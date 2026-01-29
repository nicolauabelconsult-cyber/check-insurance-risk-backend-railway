import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_perm
from ..models import Entity, EntityType, EntityStatus
from ..schemas import EntityOut, EntityCreate, EntityUpdate
from ..audit import log

router = APIRouter(prefix="/entities", tags=["entities"])

@router.get("", response_model=list[EntityOut])
def list_entities(db: Session = Depends(get_db), u=Depends(require_perm("entities:read"))):
    ents = db.query(Entity).order_by(Entity.name.asc()).all()
    return [EntityOut(id=e.id, name=e.name, type=e.type.value, status=e.status.value) for e in ents]

@router.post("", response_model=EntityOut)
def create_entity(body: EntityCreate, db: Session = Depends(get_db), u=Depends(require_perm("entities:create"))):
    e = Entity(
        id=str(uuid.uuid4()),
        name=body.name,
        type=EntityType(body.type),
        status=EntityStatus.ACTIVE,
    )
    db.add(e)
    db.commit()
    log(db, "ENTITY_CREATED", actor=u, entity=e, target_ref=e.name)
    return EntityOut(id=e.id, name=e.name, type=e.type.value, status=e.status.value)

@router.patch("/{entity_id}", response_model=EntityOut)
def update_entity(entity_id: str, body: EntityUpdate, db: Session = Depends(get_db), u=Depends(require_perm("entities:update"))):
    e = db.get(Entity, entity_id)
    if not e:
        raise HTTPException(status_code=404, detail="Not found")
    if body.name is not None:
        e.name = body.name
    if body.type is not None:
        e.type = EntityType(body.type)
    db.commit()
    log(db, "ENTITY_UPDATED", actor=u, entity=e, target_ref=e.id)
    return EntityOut(id=e.id, name=e.name, type=e.type.value, status=e.status.value)

@router.post("/{entity_id}/disable", response_model=EntityOut)
def disable_entity(entity_id: str, db: Session = Depends(get_db), u=Depends(require_perm("entities:disable"))):
    e = db.get(Entity, entity_id)
    if not e:
        raise HTTPException(status_code=404, detail="Not found")
    e.status = EntityStatus.DISABLED
    db.commit()
    log(db, "ENTITY_DISABLED", actor=u, entity=e, target_ref=e.id)
    return EntityOut(id=e.id, name=e.name, type=e.type.value, status=e.status.value)
