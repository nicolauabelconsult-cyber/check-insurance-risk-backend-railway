from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, case, Integer, cast
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_perm
from app.models import AuditLog, Entity, Risk, Source, User, UserRole

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _dashboard_entity_scope(u: User, requested_entity_id: Optional[str]) -> Optional[str]:
    """
    Opção 2:
      - SUPER_ADMIN: pode ver tudo (None) ou filtrar por ?entity_id=
      - ADMIN: apenas entity_id do próprio utilizador (obrigatório existir)
      - outros: proibido via RBAC (nem chegam aqui)
    """
    if u.role == UserRole.SUPER_ADMIN:
        return requested_entity_id  # None => global, string => filtrado

    if u.role == UserRole.ADMIN:
        if not u.entity_id:
            raise HTTPException(status_code=400, detail="ADMIN requires user.entity_id for scoped dashboard")
        return u.entity_id

    # por segurança (na prática RBAC já bloqueia)
    raise HTTPException(status_code=403, detail="Not allowed")


@router.get("/summary")
def dashboard_summary(
    entity_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("dashboard:read")),
):
    scope_entity_id = _dashboard_entity_scope(u, entity_id)

    # --- base queries com filtro por entidade (quando aplicável)
    def _apply_entity_filter(q, model_entity_col):
        if scope_entity_id:
            return q.filter(model_entity_col == scope_entity_id)
        return q

    # Totais
    q_entities = db.query(func.count(Entity.id))
    if scope_entity_id:
        q_entities = q_entities.filter(Entity.id == scope_entity_id)
    entities_count = int(q_entities.scalar() or 0)

    q_users = db.query(func.count(User.id))
    if scope_entity_id:
        q_users = q_users.filter(User.entity_id == scope_entity_id)
    users_count = int(q_users.scalar() or 0)

    q_sources = db.query(func.count(Source.id))
    q_sources = _apply_entity_filter(q_sources, Source.entity_id)
    sources_count = int(q_sources.scalar() or 0)

    q_risks = db.query(func.count(Risk.id))
    q_risks = _apply_entity_filter(q_risks, Risk.entity_id)
    risks_total = int(q_risks.scalar() or 0)

    # Últimos 200 riscos (para dashboard)
    q_risks200 = db.query(Risk).order_by(Risk.created_at.desc()).limit(200)
    q_risks200 = _apply_entity_filter(q_risks200, Risk.entity_id)
    risks_200 = q_risks200.all()

    # KPI score (Risk.score é string no teu modelo)
    scores = []
    for r in risks_200:
        try:
            scores.append(int(r.score) if r.score is not None else None)
        except Exception:
            scores.append(None)
    scores_clean = [s for s in scores if isinstance(s, int)]

    avg_score = int(round(sum(scores_clean) / len(scores_clean))) if scores_clean else 0
    high = len([s for s in scores_clean if s >= 80])
    med = len([s for s in scores_clean if 60 <= s < 80])
    low = len([s for s in scores_clean if s < 60])

    # Últimos riscos (top 10)
    latest_risks = []
    for r in risks_200[:10]:
        latest_risks.append(
            {
                "id": r.id,
                "name": r.query_name,
                "score": r.score,
                "status": getattr(r.status, "value", str(r.status)),
                "entity_id": r.entity_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )

    # Auditoria (top ações + últimos eventos)
    q_audit = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)
    if scope_entity_id:
        # No teu AuditLog tens entity_id opcional. Se for sempre preenchido, ótimo.
        # Se não for, isto ainda funciona para eventos que registram entity_id.
        q_audit = q_audit.filter(AuditLog.entity_id == scope_entity_id)
    audit_200 = q_audit.all()

    # top actions
    q_top = db.query(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action)
    if scope_entity_id:
        q_top = q_top.filter(AuditLog.entity_id == scope_entity_id)
    top_actions_rows = q_top.order_by(func.count(AuditLog.id).desc()).limit(6).all()

    top_actions = [{"action": a, "count": int(c)} for a, c in top_actions_rows]

    latest_events = []
    for a in audit_200[:6]:
        latest_events.append(
            {
                "id": a.id,
                "action": a.action,
                "actor_name": a.actor_name,
                "entity_id": a.entity_id,
                "entity_name": a.entity_name,
                "target_ref": a.target_ref,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
        )

    # Série 30 dias (para Recharts)
    # Usamos DATE(created_at) para agrupar por dia.
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=30)

    q_series = db.query(
        func.date(Risk.created_at).label("d"),
        func.count(Risk.id).label("c"),
    ).filter(Risk.created_at >= start)

    q_series = _apply_entity_filter(q_series, Risk.entity_id)
    q_series = q_series.group_by(func.date(Risk.created_at)).order_by(func.date(Risk.created_at)).all()

    series_30d = [{"date": str(d), "count": int(c)} for d, c in q_series]

    return {
        "scope_entity_id": scope_entity_id,  # útil para debug no frontend
        "entities": entities_count,
        "users": users_count,
        "sources": sources_count,
        "risks_total": risks_total,
        "risks_last_200": len(risks_200),
        "score_avg": avg_score,
        "score_high": high,
        "score_med": med,
        "score_low": low,
        "latest_risks": latest_risks,
        "top_actions": top_actions,
        "latest_events": latest_events,
        "series_30d": series_30d,
    }
