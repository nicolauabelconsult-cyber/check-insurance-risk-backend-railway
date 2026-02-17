# app/routers/dashboard.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Literal, Dict, Any, List

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.deps import get_db
from app.security import require_perm  # ou de onde vem o require_perm no teu projeto
from app.models import User, UserRole, Risk, Entity, AuditLog, Source  # ajusta se algum nome for diferente

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

Period = Literal["7d", "30d", "90d", "12m"]
Granularity = Literal["day", "week"]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _period_start(period: Period) -> datetime:
    now = _now_utc()
    if period == "7d":
        return now - timedelta(days=7)
    if period == "30d":
        return now - timedelta(days=30)
    if period == "90d":
        return now - timedelta(days=90)
    # 12m ~ 365d (suficientemente bom para dashboard executivo)
    return now - timedelta(days=365)


def _bucket_case(score_col):
    # Ajusta os thresholds se a tua política interna for outra
    # Aqui: High >= 80, Medium >= 50, Low < 50
    return case(
        (score_col >= 80, "High"),
        (score_col >= 50, "Medium"),
        else_="Low",
    )


def _apply_entity_scope(q, user: User, entity_id: Optional[str]):
    """
    Escopo:
    - SUPER_ADMIN / ADMIN podem ver tudo (ou filtrar por entity_id se enviado)
    - CLIENT_* só podem ver a sua entity_id
    """
    if user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        if entity_id:
            return q.filter(Risk.entity_id == entity_id)
        return q

    # CLIENT_*: força entity_id do user
    if not getattr(user, "entity_id", None):
        raise HTTPException(status_code=403, detail="Entity scope missing for this user")
    return q.filter(Risk.entity_id == user.entity_id)


def _apply_entity_scope_audit(q, user: User, entity_id: Optional[str]):
    if user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        if entity_id:
            return q.filter(AuditLog.entity_id == entity_id)
        return q

    if not getattr(user, "entity_id", None):
        raise HTTPException(status_code=403, detail="Entity scope missing for this user")
    return q.filter(AuditLog.entity_id == user.entity_id)


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("dashboard:read")),
    period: Period = Query("30d"),
    entity_id: Optional[str] = Query(None),
    audit_limit: int = Query(200, ge=10, le=500),
) -> Dict[str, Any]:
    start = _period_start(period)

    # ---- KPIs base ----
    # Entidades
    entities_q = db.query(func.count(Entity.id))
    if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        # para clientes, "entidades" é 1 (a sua)
        entities_count = 1 if getattr(u, "entity_id", None) else 0
    else:
        entities_count = entities_q.scalar() or 0
        if entity_id:
            entities_count = 1  # está a filtrar uma entidade específica

    # Utilizadores
    users_q = db.query(func.count(User.id))
    if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        users_q = users_q.filter(User.entity_id == u.entity_id)
        users_count = users_q.scalar() or 0
    else:
        if entity_id:
            users_q = users_q.filter(User.entity_id == entity_id)
        users_count = users_q.scalar() or 0

    # Fontes
    sources_q = db.query(func.count(Source.id))
    if u.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        if entity_id:
            sources_q = sources_q.filter(Source.entity_id == entity_id)
    else:
        sources_q = sources_q.filter(Source.entity_id == u.entity_id)
    sources_count = sources_q.scalar() or 0

    # Análises no período (Risk)
    risks_q = db.query(Risk).filter(Risk.created_at >= start)
    risks_q = _apply_entity_scope(risks_q, u, entity_id)

    analyses_count = risks_q.count()

    # Score médio no período
    avg_score = (
        db.query(func.avg(Risk.score))
        .filter(Risk.created_at >= start)
    )
    avg_score = _apply_entity_scope(avg_score, u, entity_id)
    avg_score_val = avg_score.scalar()
    avg_score_val = float(avg_score_val) if avg_score_val is not None else 0.0

    # Distribuição (High/Medium/Low)
    bucket = _bucket_case(Risk.score)
    dist_rows = (
        db.query(bucket.label("bucket"), func.count(Risk.id).label("count"))
        .filter(Risk.created_at >= start)
    )
    dist_rows = _apply_entity_scope(dist_rows, u, entity_id)
    dist_rows = dist_rows.group_by("bucket").all()

    distribution = {"High": 0, "Medium": 0, "Low": 0}
    for r in dist_rows:
        distribution[str(r.bucket)] = int(r.count)

    # Últimas análises (para tabela)
    last_risks = (
        db.query(
            Risk.id,
            Risk.name,
            Risk.score,
            Risk.status,
            Risk.entity_id,
            Risk.created_at,
        )
        .filter(Risk.created_at >= start)
    )
    last_risks = _apply_entity_scope(last_risks, u, entity_id)
    last_risks = last_risks.order_by(Risk.created_at.desc()).limit(10).all()

    last_analyses = [
        {
            "id": str(r.id),
            "name": r.name,
            "score": int(r.score or 0),
            "status": getattr(r, "status", None),
            "entity_id": str(r.entity_id) if r.entity_id else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in last_risks
    ]

    # Top auditoria por ação no período
    audit_q = (
        db.query(AuditLog.action.label("action"), func.count(AuditLog.id).label("count"))
        .filter(AuditLog.created_at >= start)
    )
    audit_q = _apply_entity_scope_audit(audit_q, u, entity_id)
    audit_top = audit_q.group_by(AuditLog.action).order_by(func.count(AuditLog.id).desc()).limit(7).all()

    audit_top_actions = [{"action": str(a.action), "count": int(a.count)} for a in audit_top]

    return {
        "period": period,
        "entity_id": entity_id,
        "kpis": {
            "entities": int(entities_count),
            "users": int(users_count),
            "sources": int(sources_count),
            "analyses": int(analyses_count),
            "avg_score": round(avg_score_val, 2),
            "distribution": distribution,
        },
        "last_analyses": last_analyses,
        "audit_top_actions": audit_top_actions,
    }


@router.get("/distribution")
def dashboard_distribution(
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("dashboard:read")),
    period: Period = Query("30d"),
    entity_id: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    start = _period_start(period)
    bucket = _bucket_case(Risk.score)

    q = (
        db.query(bucket.label("bucket"), func.count(Risk.id).label("count"))
        .filter(Risk.created_at >= start)
    )
    q = _apply_entity_scope(q, u, entity_id)
    rows = q.group_by("bucket").all()

    base = {"High": 0, "Medium": 0, "Low": 0}
    for r in rows:
        base[str(r.bucket)] = int(r.count)

    return [
        {"bucket": "High", "count": base["High"]},
        {"bucket": "Medium", "count": base["Medium"]},
        {"bucket": "Low", "count": base["Low"]},
    ]


@router.get("/trends")
def dashboard_trends(
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("dashboard:read")),
    period: Period = Query("30d"),
    entity_id: Optional[str] = Query(None),
    granularity: Granularity = Query("day"),
) -> List[Dict[str, Any]]:
    start = _period_start(period)

    # Postgres: date_trunc('day'|'week', timestamp)
    trunc_unit = "day" if granularity == "day" else "week"
    date_key = func.date_trunc(trunc_unit, Risk.created_at).label("date")

    q = (
        db.query(
            date_key,
            func.avg(Risk.score).label("avg_score"),
            func.count(Risk.id).label("count"),
        )
        .filter(Risk.created_at >= start)
    )
    q = _apply_entity_scope(q, u, entity_id)
    q = q.group_by(date_key).order_by(date_key.asc())

    rows = q.all()

    return [
        {
            "date": (r.date.isoformat() if hasattr(r.date, "isoformat") else str(r.date)),
            "avg_score": round(float(r.avg_score or 0.0), 2),
            "count": int(r.count or 0),
        }
        for r in rows
    ]
