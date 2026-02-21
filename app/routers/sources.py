import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_perm
from app.models import Source, SourceStatus, Entity
from app.schemas import SourceCreate, SourceOut, SourceUpdate
from app.audit import log

router = APIRouter(prefix="/sources", tags=["sources"])

ALLOWED_SECTORS = ["BANKING", "INSURANCE", "PENSION", "BROKER", "OTHER"]

def _resolve_entity_id(db: Session, entity_id_or_name: str) -> str:
    """Accept either Entity.id (uuid string) or Entity.name (sector enum).

    This avoids 500s when callers pass 'BANKING' instead of the entity UUID.
    """
    if not entity_id_or_name:
        return entity_id_or_name
    key = entity_id_or_name.strip()
    # If user passed a sector name, map it to the entity UUID
    if key.upper() in ALLOWED_SECTORS:
        ent = db.query(Entity).filter(Entity.name == key.upper()).first()
        if not ent:
            raise HTTPException(status_code=400, detail=f"Sector '{key}' not found in entities table.")
        return ent.id
    # Otherwise, validate that the entity exists (so we return 400 instead of 500 FK error)
    ent = db.query(Entity).filter(Entity.id == key).first()
    if not ent:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity_id '{key}'. Use a valid Entity.id UUID or one of: {', '.join(ALLOWED_SECTORS)}",
        )
    return ent.id

@router.get("", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db), u=Depends(require_perm("sources:read"))):
    q = db.query(Source)
    # scoping por entidade
    if u.entity_id:
        q = q.filter(Source.entity_id == u.entity_id)
    srcs = q.order_by(Source.name.asc()).all()
    return [SourceOut(
        id=s.id, entity_id=s.entity_id, name=s.name, category=s.category, collected_from=s.collected_from, status=s.status.value
    ) for s in srcs]

@router.post("", response_model=SourceOut)
def create_source(body: SourceCreate, db: Session = Depends(get_db), u=Depends(require_perm("sources:create"))):
    # Produção V1: apenas SUPER_ADMIN pode criar fontes
    role_val = getattr(getattr(u, "role", None), "value", getattr(u, "role", None))
    if role_val != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Only SUPER_ADMIN can create sources")

    entity_id = body.entity_id or u.entity_id
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    # Accept either sector name (BANKING/INSURANCE/...) or the actual Entity UUID.
    entity_id = _resolve_entity_id(db, entity_id)

    s = Source(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        name=body.name,
        category=body.category,
        collected_from=body.collected_from,
        status=SourceStatus.ACTIVE,
    )
    db.add(s)
    db.commit()
    log(db, "SOURCE_CREATED", actor=u, entity=None, target_ref=s.name, meta={"entity_id": s.entity_id})
    return SourceOut(
        id=s.id, entity_id=s.entity_id, name=s.name, category=s.category, collected_from=s.collected_from, status=s.status.value
    )

@router.patch("/{source_id}", response_model=SourceOut)
def update_source(source_id: str, body: SourceUpdate, db: Session = Depends(get_db), u=Depends(require_perm("sources:update"))):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    if u.entity_id and s.entity_id != u.entity_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if body.name is not None:
        s.name = body.name
    if body.category is not None:
        s.category = body.category
    if body.collected_from is not None:
        s.collected_from = body.collected_from
    if body.status is not None:
        s.status = SourceStatus(body.status)

    db.commit()
    log(db, "SOURCE_UPDATED", actor=u, entity=None, target_ref=s.id)
    return SourceOut(
        id=s.id, entity_id=s.entity_id, name=s.name, category=s.category, collected_from=s.collected_from, status=s.status.value
    )

@router.post("/{source_id}/disable", response_model=SourceOut)
def disable_source(source_id: str, db: Session = Depends(get_db), u=Depends(require_perm("sources:disable"))):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    if u.entity_id and s.entity_id != u.entity_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    s.status = SourceStatus.DISABLED
    db.commit()
    log(db, "SOURCE_DISABLED", actor=u, entity=None, target_ref=s.id)
    return SourceOut(
        id=s.id, entity_id=s.entity_id, name=s.name, category=s.category, collected_from=s.collected_from, status=s.status.value
    )
