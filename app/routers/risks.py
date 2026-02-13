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

@router.get("", response_model=list[RiskOut])
def list_risks(db: Session = Depends(get_db), u: User = Depends(require_perm("risk:read"))):
    q = db.query(Risk)
    if u.entity_id:
        q = q.filter(Risk.entity_id == u.entity_id)

    rows = q.order_by(Risk.created_at.desc()).limit(200).all()
    return [_risk_to_out(r) for r in rows]


@router.get("/{risk_id}", response_model=RiskOut)
def get_risk(risk_id: str, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:read"))):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Risk not found")
    _guard_risk_scope(u, r)
    return _risk_to_out(r)


@router.post("/search", response_model=RiskSearchOut)
def search_risk(body: RiskSearchIn, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:create"))):
    entity_id = _resolve_entity_id(u, getattr(body, "entity_id", None))

    base = (body.name or "").strip()
    if not base:
        raise HTTPException(status_code=400, detail="name is required")

    candidates = []
    for i in range(1, 4):
        cid = str(uuid.uuid4())
        candidates.append(
            CandidateOut(
                id=cid,
                full_name=f"{base} {i}",
                nationality=body.nationality,
                dob=None,
                doc_type=None,
                doc_last4=None,
                sources=["OFAC", "UN", "Local Watchlists"],
                match_score=90 - (i * 7),
            )
        )

    log(db, "RISK_SEARCH", actor=u, entity=None, target_ref=base, meta={"entity_id": entity_id})

    return RiskSearchOut(disambiguation_required=True, candidates=candidates)


@router.post("/confirm", response_model=RiskOut)
def confirm_risk(body: RiskConfirmIn, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:confirm"))):
    entity_id = _resolve_entity_id(u, getattr(body, "entity_id", None))

    # Mock scoring (motor real depois)
    score_int = 78
    score = str(score_int)

    summary = (
        "Avaliação mock concluída. Preparado para motor real (KYC/AML/PEP) com rastreabilidade de motivos."
    )
    matches = [
        {"source": "OFAC", "match": True, "confidence": 0.82, "note": "Similaridade de nome (mock)"}
    ]

    r = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        query_name=body.name,
        query_nationality=body.nationality,
        query_bi=body.id_number if body.id_type == "BI" else None,
        query_passport=body.id_number if body.id_type == "PASSPORT" else None,
        score=score,
        summary=summary,
        matches=matches,
        status=RiskStatus.DONE,
        created_by=u.id,
        created_at=datetime.utcnow(),
    )
    db.add(r)
    db.commit()

    # Underwriting (pagamentos/sinistros/apólices/fraude/cancelamentos)
    uw = compute_underwriting(
        db=db,
        entity_id=entity_id,
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

    log(db, "RISK_CONFIRM", actor=u, entity=None, target_ref=r.id, meta={"entity_id": entity_id, "score": score_int})

    return _risk_to_out(r)


@router.get("/{risk_id}/pdf")
def risk_pdf(risk_id: str, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:pdf:download"))):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Risk not found")
    _guard_risk_scope(u, r)

    # garante underwriting para risks antigos
    _ensure_underwriting(db, r)

    integrity_hash = make_integrity_hash(r)
    verify_url = f"{settings.BASE_URL}/verify/{r.id}/{integrity_hash}"
    server_signature = make_server_signature(integrity_hash)

    try:
        pdf_bytes = build_risk_pdf_institutional(
            risk=r,
            analyst_name=u.name,
            generated_at=datetime.utcnow(),
            integrity_hash=integrity_hash,
            server_signature=server_signature,
            verify_url=verify_url,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {type(e).__name__}: {e}")

    log(
        db,
        "RISK_PDF_DOWNLOAD",
        actor=u,
        entity=None,
        target_ref=r.id,
        meta={"entity_id": r.entity_id, "hash": integrity_hash},
    )

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="risk_{r.id}.pdf"'},
    )
