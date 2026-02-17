import uuid
from sqlalchemy.orm import Session
from .models import AuditLog

def log(db: Session, action: str, actor=None, entity=None, target_ref: str | None = None, meta: dict | None = None):
    rec = AuditLog(
        id=str(uuid.uuid4()),
        action=action,
        actor_id=getattr(actor, "id", None) if actor else None,
        actor_name=getattr(actor, "name", "Unknown") if actor else "Unknown",
        entity_id=getattr(entity, "id", None) if entity else None,
        entity_name=getattr(entity, "name", None) if entity else None,
        target_ref=target_ref,
        meta=meta or {},
    )
    db.add(rec)
    db.commit()
