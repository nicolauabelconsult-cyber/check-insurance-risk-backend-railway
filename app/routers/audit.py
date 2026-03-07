from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import require_perm
from app.models import AuditLog
from app.schemas import AuditOut

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("", response_model=list[AuditOut])
def list_audit(db: Session = Depends(get_db), u=Depends(require_perm("audit:read"))):
    q = db.query(AuditLog)
    if u.entity_id:
        q = q.filter(AuditLog.entity_id == u.entity_id)
    rows = q.order_by(AuditLog.created_at.desc()).limit(200).all()
    return [AuditOut(
        id=a.id, action=a.action, actor_name=a.actor_name, entity_name=a.entity_name,
        target_ref=a.target_ref, meta=a.meta, created_at=a.created_at.isoformat()
    ) for a in rows]
