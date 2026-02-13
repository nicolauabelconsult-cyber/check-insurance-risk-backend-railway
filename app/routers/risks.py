from __future__ import annotations

import uuid
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_perm
from app.models import Risk, RiskStatus, User, UserRole
from app.schemas import CandidateOut, RiskConfirmIn, RiskOut, RiskSearchIn, RiskSearchOut
from app.audit import log
from app.settings import settings
from app.pdfs import build_risk_pdf_institutional, make_integrity_hash, make_server_signature
from app.services.underwriting import compute_underwriting

router = APIRouter(prefix="/risks", tags=["risks"])


# -------------------------
# Multi-tenant utilities
# -------------------------

def _resolve_entity_id(u: User, requested: str | None) -> str:
    if u.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        if not requested:
            raise HTTPException(status_code=400, detail="entity_id required for admins")
        return requested
    if not u.entity_id:
        raise HTTPException(status_code=400, detail="User entity_id missing")
    return u.entity_id


def _guard_risk_scope(u: User, r: Risk):
    if u.entity_id and r.entity_id != u.entity_id:
        raise HTTPException(status_code=404, detail="Risk not found")


def _risk_to_out(r: Risk) -> RiskOut:
    return RiskOut(
        id=r.id,
        entity_id=r.entity_id,
        name=r.query_name,
        bi=r.query_bi,
        passport=r.query_passport,
        nationality=r.query_nationality,
        score=r.score,
        summary=r.summary,
        matches=r.matches or [],
        status=getattr(r.status, "value", str(r.status)),
    )


def _ensure_underwriting(db: Session, r: Risk):
    """
    Garante underwriting calculado e persistido.
    (Importante para risks antigos criados antes desta fase.)
    """
    if getattr(r, "uw_score", None) is not None:
        return

    uw = compute_underwriting(
        db=db,
        entity_id=r.entity_id,
        bi=r.query_bi,
        passport=r.query_passport,
        full_name=r.query_name,
    )

    r.uw_score = uw["uw_score"]
    r.uw_decision = uw["uw_decision"]
    r.uw_summary = uw["uw_summary"]
    r.uw_kpis = uw["uw_kpis"]
    r.uw_factors = uw["uw_factors"]
    db.add(r)
    db.commit()


# -------------------------
# Endpoints
# -------------------------

@router.post("/confirm", response_model=RiskOut)
def confirm_risk(body: RiskConfirmIn, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:confirm"))):
    entity_id = _resolve_entity_id(u, body.entity_id)

    score_int = 50
    score = str(score_int)

    from app.services.compliance_matching import pep_match

    pep_hits = pep_match(
        db=db,
        entity_id=entity_id,
        full_name=body.name,
        bi=body.id_number if body.id_type == "BI" else None,
        passport=body.id_number if body.id_type == "PASSPORT" else None,
    )

    if pep_hits:
        score_int = 85
        score = str(score_int)

    summary = "Avaliação baseada em triagem PEP interna."

    r = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        query_name=body.name,
        query_nationality=body.nationality,
        query_bi=body.id_number if body.id_type == "BI" else None,
        query_passport=body.id_number if body.id_type == "PASSPORT" else None,
        score=score,
        summary=summary,
        matches=pep_hits,
        status=RiskStatus.DONE,
        created_by=u.id,
        created_at=datetime.utcnow(),
    )
    db.add(r)
    db.commit()

    return _risk_to_out(r)
