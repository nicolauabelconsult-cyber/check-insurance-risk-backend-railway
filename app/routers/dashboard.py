# app/routers/dashboard.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Literal, Dict, Any, List

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func, case, cast, Float
from sqlalchemy.orm import Session

from app.deps import get_db, require_perm
from app.models import User, UserRole, Risk, Entity, AuditLog, Source

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
    return now - timedelta(days=365)  # 12m ~ 365d


def _score_num():
    """
    Cast seguro do score (VARCHAR) para número.
    - Se for numérico: converte para Float
    - Se não for numérico: NULL (avg ignora NULL)
    """
    is_numeric = Risk.score.op("~")(r"^\s*\d+(\.\d+)?\s*$")  # regex postgres
    return case(
        (is_numeric, cast(func.trim(Risk.score), Float)),
        else_=None,
    )


def _bucket_case(score_num_col):
    """
    Buckets:
    - High >= 80
    - Medium >= 50
    - Low < 50
    Score inválido -> NULL -> coalesce para 0 -> Low
    """
    score_for_bucket = func.coalesce(score_num_col, 0.0)
    return case(
        (score_for_bucket >= 80, "High"),
        (score_for_bucket >= 50, "Medium"),
        else_="Low",
    )


def _apply_entity_scope_risk(q, user: User, entity_id: Optional[str]):
    """
    Escopo:
    - SUPER_ADMIN / ADMIN: vê tudo (ou filtra por entity_id se enviado)
    - CLIENT_*: vê apenas a sua entity_id
    """
    if user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        if entity_id:
            return q.filter(Risk.entity_id == entity_id)
        return q

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

    # -----------------------------
    # KPIs base
    # -----------------------------
    # Entidades
    entities_q = db.query(func.count(Entity.id))
    if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        entities_count = 1 if getattr(u, "entity_id", None) else 0
    else:
        entities_count = entities_q.scalar() or 0
        if entity_id:
            entities_count = 1

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

    # Total de risks (vida inteira)
    risks_total_q = db.query(func.count(Risk.id))
    risks_total_q = _apply_entity_scope_risk(risks_total_q, u, entity_id)
    risks_total = risks_total_q.scalar() or 0

    # Risks no período (para KPIs do período)
    risks_period_q = db.query(Risk).filter(Risk.created_at >= start)
    risks_period_q = _apply_entity_scope_risk(risks_period_q, u, entity_id)
    analyses_count = risks_period_q.count()

    # Score médio no período (CAST seguro)
    score_num = _score_num()
    avg_score_q = db.query(func.avg(score_num)).filter(Risk.created_at >= start)
    avg_score_q = _apply_entity_scope_risk(avg_score_q, u, entity_id)
    avg_score_val = avg_score_q.scalar()
    avg_score_val = float(avg_score_val) if avg_score_val is not None else 0.0

    # Distribuição High/Medium/Low no período
    bucket = _bucket_case(score_num)
    dist_q = (
        db.query(bucket.label("bucket"), func.count(Risk.id).label("count"))
        .filter(Risk.created_at >= start)
    )
    dist_q = _apply_entity_scope_risk(dist_q, u, entity_id)
    dist_rows = dist_q.group_by("bucket").all()

    distribution = {"High": 0, "Medium": 0, "Low": 0}
    for r in dist_rows:
        distribution[str(r.bucket)] = int(r.count)

    # -----------------------------
    # Últimas análises (tabela)
    # -----------------------------
    # ⚠️ Risk NÃO tem "name". O campo correto é query_name.
    last_q = (
        db.query(
            Risk.id,
            Risk.query_name,
            Risk.score,
            Risk.status,
            Risk.entity_id,
            Risk.created_at,
        )
        .filter(Risk.created_at >= start)
    )
    last_q = _apply_entity_scope_risk(last_q, u, entity_id)
    last_rows = last_q.order_by(Risk.created_at.desc()).limit(10).all()

    last_analyses = [
        {
            "id": str(r.id),
            "name": r.query_name,          # <- devolvemos como "name" para compatibilidade do frontend
            "score": r.score,              # mantém string como no teu sistema
            "status": str(r.status) if r.status is not None else None,
            "entity_id": str(r.entity_id) if r.entity_id else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in last_rows
    ]

    # -----------------------------
    # Top auditoria por ação (período)
    # -----------------------------
    audit_q = (
        db.query(AuditLog.action.label("action"), func.count(AuditLog.id).label("count"))
        .filter(AuditLog.created_at >= start)
    )
    audit_q = _apply_entity_scope_audit(audit_q, u, entity_id)
    audit_top = (
        audit_q.group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .limit(7)
        .all()
    )
    audit_top_actions = [{"action": str(a.action), "count": int(a.count)} for a in audit_top]

    return {
        "period": period,
        "entity_id": entity_id,
        "kpis": {
            "entities": int(entities_count),
            "users": int(users_count),
            "sources": int(sources_count),
            "risks_total": int(risks_total),
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

    score_num = _score_num()
    bucket = _bucket_case(score_num)

    q = (
        db.query(bucket.label("bucket"), func.count(Risk.id).label("count"))
        .filter(Risk.c
