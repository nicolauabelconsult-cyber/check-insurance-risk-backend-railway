from __future__ import annotations

import uuid
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_perm
from app.models import User, UserRole
from app.audit import log
from app.compliance_models import PepRecord

router = APIRouter(prefix="/compliance", tags=["compliance"])


def _resolve_entity_id(u: User, requested: str | None) -> str:
    if u.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        if not requested:
            raise HTTPException(status_code=400, detail="entity_id required")
        return requested
    return u.entity_id


class PepRecordIn(BaseModel):
    entity_id: str | None = None
    full_name: str
    aka: str | None = None
    bi: str | None = None
    passport: str | None = None
    dob: date | None = None
    nationality: str | None = None
    pep_category: str | None = None
    pep_role: str | None = None
    country: str | None = None
    risk_level: str | None = None
    source_name: str | None = "PEP_INTERNAL"
    source_ref: str | None = None
    note: str | None = None


@router.post("/pep/bulk")
def upload_pep_bulk(
    items: list[PepRecordIn],
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("compliance:upload")),
):
    inserted = 0

    for it in items:
        entity_id = _resolve_entity_id(u, it.entity_id)

        row = PepRecord(
            id=str(uuid.uuid4()),
            entity_id=entity_id,
            full_name=it.full_name.strip(),
            aka=it.aka,
            bi=it.bi,
            passport=it.passport,
            dob=it.dob,
            nationality=it.nationality,
            pep_category=it.pep_category,
            pep_role=it.pep_role,
            country=it.country,
            risk_level=(it.risk_level.upper() if it.risk_level else None),
            source_name=it.source_name or "PEP_INTERNAL",
            source_ref=it.source_ref,
            note=it.note,
        )
        db.add(row)
        inserted += 1

    db.commit()

    log(db, "PEP_UPLOAD", actor=u, entity=None, target_ref=str(inserted), meta={"rows": inserted})
    return {"inserted": inserted}
