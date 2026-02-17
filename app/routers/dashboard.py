from __future__ import annotations

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.deps import require_perm
from app.models import Risk, User, AuditLog, RiskStatus

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("dashboard:read")),
):
    # Janela de 30 dias (podes mudar)
    since = datetime.utcnow() - timedelta(days=30)

    total_risks = db.query(func.count(Risk.id)).scalar() or 0
    risks_30d = db.query(func.count(Risk.id)).filter(Risk.created_at >= since).scalar() or 0

    done_risks = db.query(func.count(Risk.id)).filter(Risk.status == RiskStatus.DONE).scalar() or 0
    draft_risks = db.query(func.count(Risk.id)).filter(Risk.status == RiskStatus.DRAFT).scalar() or 0

    # Distribuição por entidade (top 10)
    by_entity = (
        db.query(Risk.entity_id, func.count(Risk.id))
        .group_by(Risk.entity_id)
        .order_by(func.count(Risk.id).desc())
        .limit(10)
        .all()
    )
    by_entity_out = [{"entity_id": eid, "count": int(cnt)} for (eid, cnt) in by_entity]

    # Ações de auditoria (30 dias, top 12)
    audit_actions = (
        db.query(AuditLog.action, func.count(AuditLog.id))
        .filter(AuditLog.created_at >= since)
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .limit(12)
        .all()
    )
    audit_actions_out = [{"action": a, "count": int(cnt)} for (a, cnt) in audit_actions]

    return {
        "window_days": 30,
        "total_risks": int(total_risks),
        "risks_30d": int(risks_30d),
        "done_risks": int(done_risks),
        "draft_risks": int(draft_risks),
        "top_entities": by_entity_out,
        "audit_actions": audit_actions_out,
    }
