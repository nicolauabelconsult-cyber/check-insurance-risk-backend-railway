import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_perm
from app.models import Entity, EntityType, EntityStatus
from app.schemas import EntityOut, EntityCreate, EntityUpdate
from app.audit import log

router = APIRouter(prefix="/entities", tags=["entities"])

@router.get("", response_model=list[EntityOut])
def list_entities(db: Session = Depends(get_db), u=Depends(require_perm("entities:read"))):
    rows = db.query(Entity).order_by(Entity.created_at.desc()).all()
    return [EntityOut(id=e.id, name=e.name, type=e.type.value, status=e.status.value) for e in rows]

@router.post("", response_model=EntityOut)
def create_entity(data: EntityCreate, db: Session = Depends(get_db), u=Depends(require_perm("entities:create"))):
    e = Entity(
        id=str(uuid.uuid4()),
        name=data.name.strip(),
        type=EntityType(data.type),
        status=EntityStatus.ACTIVE,
    )
    db.add(e)
    db.commit()
    log(db, "ENTITY_CREATED", actor=u, entity=e, target_ref=e.id)
    return EntityOut(id=e.id, name=e.name, type=e.type.value, status=e.status.value)

@router.patch("/{entity_id}", response_model=EntityOut)
def update_entity(entity_id: str, data: EntityUpdate, db: Session = Depends(get_db), u=Depends(require_perm("entities:update"))):
    e = db.get(Entity, entity_id)
    if not e:
        raise HTTPException(status_code=404, detail="Entity not found")

    if data.name is not None:
        e.name = data.name.strip()
    if data.type is not None:
        e.type = EntityType(data.type)
    if data.status is not None:
        e.status = EntityStatus(data.status)

    db.commit()
    log(db, "ENTITY_UPDATED", actor=u, entity=e, target_ref=e.id, meta={"fields": data.model_dump(exclude_none=True)})
    return EntityOut(id=e.id, name=e.name, type=e.type.value, status=e.status.value)
