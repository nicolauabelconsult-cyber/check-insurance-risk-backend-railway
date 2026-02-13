import uuid
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_perm
from app.models import Risk, RiskStatus, User, UserRole
from app.schemas import (
    CandidateOut,
    RiskConfirmIn,
    RiskOut,
    RiskSearchIn,
    RiskSearchOut,
)
from app.audit import log
from app.settings import settings

from app.pdfs import (
    build_risk_pdf_institutional,
    make_integrity_hash,
    make_server_signature,
    matches_by_type,
)

from app.insurance_profile import build_insurance_profile
from app.underwriting_engine import final_decision


router = APIRouter(prefix="/risks", tags=["risks"])


def _resolve_entity_id(u: User, requested: str | None) -> str:
    if u.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        if not requested:
            raise HTTPException(status_code=400, detail="entity_id required for admins")
        return requested
    if not u.entity_id:
        raise HTTPException(status_code=400, detail="User entity_id missing")
    return u.entity_id


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
        status=r.status.value if hasattr(r.status, "value") else str(r.status),
    )


@router.get("", response_model=list[RiskOut])
def list_risks(db: Session = Depends(get_db), u: User = Depends(require_perm("risk:read"))):
    q = db.query(Risk)
    if u.entity_id:
        q = q.filter(Risk.entity_id == u.entity_id)
    rows = q.order_by(Risk.created_at.desc()).limit(200).all()
    return [_risk_to_out(r) for r in rows]


@router.post("/search", response_model=RiskSearchOut)
def search_risk(body: RiskSearchIn, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:create"))):
    entity_id = _resolve_entity_id(u, body.entity_id)

    # Mock engine: candidates
    base = body.name.strip()
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
    entity_id = _resolve_entity_id(u, body.entity_id)

    # Mock scoring
    score_int = 78
    score = str(score_int)
    summary = "Avaliação de risco (mock). Substituir por motor real."
    matches = [
        {
            "type": "WATCHLIST",
            "source": "OFAC",
            "match": True,
            "confidence": 0.82,
            "note": "Semelhança de nome",
        }
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

    log(
        db,
        "RISK_CONFIRM",
        actor=u,
        entity=None,
        target_ref=r.id,
        meta={"entity_id": entity_id, "score": score_int},
    )

    return _risk_to_out(r)


@router.get("/{risk_id}/pdf")
def risk_pdf(risk_id: str, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:pdf:download"))):
    """
    PDF institucional (Banco/Seguradora):
    - Multi-tenant scoped
    - QR + hash + assinatura
    - perfil segurador (Excel) + decisão final ponderada
    """
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Risk not found")

    # blindagem multi-tenant
    if u.entity_id and r.entity_id != u.entity_id:
        raise HTTPException(status_code=404, detail="Risk not found")

    # Integridade
    integrity_hash = make_integrity_hash(r)
    verify_url = f"{settings.BASE_URL}/verify/{r.id}/{integrity_hash}"
    server_signature = make_server_signature(integrity_hash)

    # 1) Perfil segurador (a partir das fontes Excel já importadas para o Postgres)
    insurance_profile = build_insurance_profile(
        db,
        entity_id=r.entity_id,
        bi=r.query_bi,
        passport=r.query_passport,
        full_name=r.query_name,
    )

    # 2) Matches agrupados (compliance)
    grouped = matches_by_type(r)

    # 3) Decisão final (hard-stops + ponderação)
    compliance_score = int(r.score) if str(r.score).isdigit() else 0
    decision = final_decision(
        compliance_score=compliance_score,
        grouped_matches=grouped,
        insurance_profile=insurance_profile,
        weights=None,  # usa DEFAULT 70/30 no engine
    )

    # 4) Anexar snapshot ao objeto (sem migrations por agora)
    setattr(r, "insurance_profile", insurance_profile)
    setattr(
        r,
        "final_decision",
        {
            "compliance_score": decision.compliance_score,
            "insurance_score": decision.insurance_score,
            "final_score": decision.final_score,
            "decision": decision.decision,
            "rationale": decision.rationale,
            "premium_hint": decision.premium_hint,
            "underwriting_actions": decision.underwriting_actions,
            "underwriting_conditions": decision.underwriting_conditions,
            "decision_drivers": decision.decision_drivers,
        },
    )

    # Build PDF
    pdf_bytes = build_risk_pdf_institutional(
        risk=r,
        analyst_name=u.name,
        generated_at=datetime.utcnow(),
        integrity_hash=integrity_hash,
        server_signature=server_signature,
        verify_url=verify_url,
    )

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
        headers={"Content-Disposition": f"attachment; filename=risk_{r.id}.pdf"},
    )
