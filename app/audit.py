import uuid
from sqlalchemy.orm import Session
from .models import AuditLog

def log(db: Session, action: str, actor=None, entity=None, target_ref: str | None = None, meta: dict | None = None):
    """Registo de auditoria.

    Produção V1:
    - Se existir entity (model Entity), usa entity.id
    - Caso contrário, tenta inferir entity_id do meta['entity_id']
    - Caso contrário, usa actor.entity_id (quando aplicável)
    """
    meta = meta or {}
    inferred_entity_id = (
        getattr(entity, "id", None)
        if entity is not None
        else meta.get("entity_id") or getattr(actor, "entity_id", None)
    )
    rec = AuditLog(
        id=str(uuid.uuid4()),
        action=action,
        actor_id=getattr(actor, "id", None) if actor else None,
        actor_name=getattr(actor, "name", "Unknown") if actor else "Unknown",
        entity_id=inferred_entity_id,
        entity_name=getattr(entity, "name", None) if entity else None,
        target_ref=target_ref,
        meta=meta,
    )
    db.add(rec)
    db.commit()
