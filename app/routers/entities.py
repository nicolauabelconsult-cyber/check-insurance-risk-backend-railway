import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import require_perm
from ..models import Entity, EntityType, EntityStatus
from ..schemas import EntityOut, EntityCreate
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
