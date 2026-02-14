from __future__ import annotations

import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_perm
from app.models import User, UserRole
from app.audit import log
from app.compliance_models import PepRecord

router = APIRouter(prefix="/compliance", tags=["compliance"])


def _resolve_entity_id(u: User, requested: Optional[str]) -> str:
    if u.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        if not requested:
            raise HTTPException(status_code=400, detail="entity_id required")
        return requested
    if not u.entity_id:
        raise HTTPException(status_code=400, detail="User entity_id missing")
    return u.entity_id


class PepRecordIn(BaseModel):
    # admins podem inserir por entidade; client ignora requested
    entity_id: Optional[str] = None

    full_name: str = Field(..., min_length=2)

    aka: Optional[str] = None
    bi: Optional[str] = None
    passport: Optional[str] = None
    dob: Optional[date] = None
    nationality: Optional[str] = None

    pep_category: Optional[str] = None
    pep_role: Optional[str] = None
    country: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    risk_level: Optional[str] = None  # LOW|MEDIUM|HIGH

    source_name: Optional[str] = "PEP_INTERNAL"
    source_ref: Optional[str] = None
    note: Optional[str] = None


@router.post("/pep/bulk")
def upload_pep_bulk(
    items: List[PepRecordIn],
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
            start_date=it.start_date,
            end_date=it.end_date,
            risk_level=(it.risk_level.upper() if it.risk_level else None),

            source_name=(it.source_name or "PEP_INTERNAL"),
            source_ref=it.source_ref,
            note=it.note,
        )
        db.add(row)
        inserted += 1

    db.commit()
    log(db, "PEP_UPLOAD_BULK", actor=u, entity=None, target_ref=str(inserted), meta={"rows": inserted})
    return {"inserted": inserted}
