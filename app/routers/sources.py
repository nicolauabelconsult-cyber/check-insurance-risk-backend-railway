import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_perm, resolve_entity_id, ensure_entity_scope
from app.models import Source, SourceStatus
from app.models_source_records import SourceRecord
from app.schemas import SourceCreate, SourceOut, SourceUpdate
from app.audit import log

router = APIRouter(prefix="/sources", tags=["sources"])


def _to_out(s: Source) -> SourceOut:
    return SourceOut(
        id=s.id,
        entity_id=s.entity_id,
        name=s.name,
        category=s.category,
        collected_from=s.collected_from,
        status=s.status.value,
    )


@router.get("", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db), u=Depends(require_perm("sources:read"))):
    q = db.query(Source)
    # scoping por entidade
    if getattr(u, "entity_id", None):
        q = q.filter(Source.entity_id == u.entity_id)
    srcs = q.order_by(Source.name.asc()).all()
    return [_to_out(s) for s in srcs]


@router.post("", response_model=SourceOut)
def create_source(body: SourceCreate, db: Session = Depends(get_db), u=Depends(require_perm("sources:create"))):

    entity_id = body.entity_id or getattr(u, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    s = Source(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        name=body.name,
        category=(body.category or "").upper().strip(),
        collected_from=(body.collected_from or getattr(body, 'origin', None) or 'INTERNAL'),
        status=SourceStatus.ACTIVE,
    )
    db.add(s)
    db.commit()
    log(db, "SOURCE_CREATED", actor=u, entity=None, target_ref=s.name, meta={"entity_id": s.entity_id})
    return _to_out(s)


@router.patch("/{source_id}", response_model=SourceOut)
def update_source(
    source_id: str,
    body: SourceUpdate,
    db: Session = Depends(get_db),
    u=Depends(require_perm("sources:update")),
):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    if getattr(u, "entity_id", None) and s.entity_id != u.entity_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if body.name is not None:
        s.name = body.name
    if body.category is not None:
        s.category = (body.category or "").upper().strip()
    if body.collected_from is not None:
        s.collected_from = body.collected_from
    if body.status is not None:
        s.status = SourceStatus(body.status)

    db.commit()
    log(db, "SOURCE_UPDATED", actor=u, entity=None, target_ref=s.id)
    return _to_out(s)


# Compatibilidade: alguns frontends usam PUT.
@router.put("/{source_id}", response_model=SourceOut)
def put_source(
    source_id: str,
    body: SourceUpdate,
    db: Session = Depends(get_db),
    u=Depends(require_perm("sources:update")),
):
    return update_source(source_id, body, db, u)


@router.post("/{source_id}/disable", response_model=SourceOut)
def disable_source(source_id: str, db: Session = Depends(get_db), u=Depends(require_perm("sources:disable"))):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    if getattr(u, "entity_id", None) and s.entity_id != u.entity_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    s.status = SourceStatus.DISABLED
    db.commit()
    log(db, "SOURCE_DISABLED", actor=u, entity=None, target_ref=s.id)
    return _to_out(s)


@router.delete("/{source_id}")
def delete_source(source_id: str, db: Session = Depends(get_db), u=Depends(require_perm("sources:delete"))):

    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    if getattr(u, "entity_id", None) and s.entity_id != u.entity_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    name = s.name

    # ✅ Apaga primeiro os source_records associados (evita 500 por FK sem cascade na DB atual)
    try:
        db.query(SourceRecord).filter(SourceRecord.source_id == source_id).delete(synchronize_session=False)
        db.delete(s)
        db.commit()
    except IntegrityError:
        db.rollback()
        # 409 = conflito (normalmente FK/constraint)
        raise HTTPException(
            status_code=409,
            detail="Não foi possível apagar a fonte. Existem registos associados (ou constraints antigas).",
        )

    log(db, "SOURCE_DELETED", actor=u, entity=None, target_ref=name)
    return Response(status_code=204)
