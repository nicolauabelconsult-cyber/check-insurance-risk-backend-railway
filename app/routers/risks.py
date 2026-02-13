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

# Se já existir no teu projecto, vai usar. Se não existir ainda, devolve underwriting neutro.
try:
    from app.services.underwriting import compute_underwriting
except Exception:  # pragma: no cover
    compute_underwriting = None  # type: ignore


router = APIRouter(prefix="/risks", tags=["risks"])


# -------------------------
# Multi-tenant utilities
# -------------------------

def _resolve_entity_id(u: User, requested: str | None) -> str:
    # ADMIN/SUPER_ADMIN precisam enviar entity_id no body
    if u.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        if not requested:
            raise HTTPException(status_code=400, detail="Selecione uma entidade (entity_id) para continuar.")
        return requested

    # CLIENT/USER usa sempre entity_id do token
    if not u.entity_id:
        raise HTTPException(status_code=400, detail="Utilizador sem entity_id associado.")
    return u.entity_id


def _guard_risk_scope(u: User, r: Risk):
    if u.entity_id and r.entity_id != u.entity_id:
        # 404 para não revelar existência
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
    Garante underwriting calculado e persistido se o modelo suportar.
    - Se ainda não tens as colunas uw_*, isto não rebenta: só ignora.
    """
    # Se não tens serviço ainda, ignora
    if compute_underwriting is None:
        return

    # Se já tiver uw_score preenchido, ignora
    if getattr(r, "uw_score", None) is not None:
        return

    uw = compute_underwriting(
        db=db,
        entity_id=r.entity_id,
        bi=r.query_bi,
        passport=r.query_passport,
        full_name=r.query_name,
    )

    # Só grava se as colunas existirem no teu model
    for k in ["uw_score", "uw_decision", "uw_summary", "uw_kpis", "uw_factors"]:
        if hasattr(r, k) and k in uw:
            setattr(r, k, uw[k])

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

    log(db, "RISK_LIST", actor=u, entity=None, target_ref=None, meta={"count": len(rows)})
    return [_risk_to_out(r) for r in rows]


@router.get("/{risk_id}", response_model=RiskOut)
def get_risk(risk_id: str, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:read"))):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Risk not found")
    _guard_risk_scope(u, r)

    _ensure_underwriting(db, r)

    log(db, "RISK_READ", actor=u, entity=None, target_ref=risk_id, meta={"entity_id": r.entity_id})
    return _risk_to_out(r)


@router.post("/search", response_model=RiskSearchOut)
def search_risk(body: RiskSearchIn, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:create"))):
    entity_id = _resolve_entity_id(u, body.entity_id)

    # Mock de candidatos (estrutura já pronta para motor real)
    base = (body.name or "").strip()
    candidates: list[CandidateOut] = []
    for i in range(1, 4):
        candidates.append(
            CandidateOut(
                id=str(uuid.uuid4()),
                full_name=f"{base} {i}".strip(),
                nationality=body.nationality,
                dob=None,
                doc_type=None,
                doc_last4=None,
                sources=["Fontes Internas", "Listas Públicas", "Watchlists"],
                match_score=90 - (i * 7),
            )
        )

    log(db, "RISK_SEARCH", actor=u, entity=None, target_ref=base, meta={"entity_id": entity_id})
    return RiskSearchOut(disambiguation_required=True, candidates=candidates)


@router.post("/confirm", response_model=RiskOut)
def confirm_risk(body: RiskConfirmIn, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:confirm"))):
    entity_id = _resolve_entity_id(u, body.entity_id)

    # --------------------------
    # Compliance matching (PEP)
    # --------------------------
    # Se o motor ainda não existir, devolve vazio e segue.
    pep_hits = []
    try:
        from app.services.compliance_matching import pep_match

        pep_hits = pep_match(
            db=db,
            entity_id=entity_id,
            full_name=body.name,
            bi=body.id_number if body.id_type == "BI" else None,
            passport=body.id_number if body.id_type == "PASSPORT" else None,
        )
    except Exception:
        pep_hits = []

    # Score base + agravamento por PEP
    score_int = 50
    if pep_hits:
        score_int = 85

    summary = "Avaliação baseada em triagem interna (PEP) e estrutura preparada para fontes reais."

    r = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        query_name=body.name,
        query_nationality=body.nationality,
        query_bi=body.id_number if body.id_type == "BI" else None,
        query_passport=body.id_number if body.id_type == "PASSPORT" else None,
        score=str(score_int),
        summary=summary,
        matches=pep_hits,
        status=RiskStatus.DONE,
        created_by=u.id,
        created_at=datetime.utcnow(),
    )

    db.add(r)
    db.commit()

    # underwriting (se existir)
    _ensure_underwriting(db, r)

    log(db, "RISK_CONFIRM", actor=u, entity=None, target_ref=r.id, meta={"entity_id": entity_id, "score": score_int})
    return _risk_to_out(r)


@router.get("/{risk_id}/pdf")
def risk_pdf(risk_id: str, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:pdf:download"))):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Risk not found")
    _guard_risk_scope(u, r)

    # garante underwriting se existir
    _ensure_underwriting(db, r)

    integrity_hash = make_integrity_hash(r)
    base_url = getattr(settings, "BASE_URL", None) or "https://checkinsurancerisk.com"
    verify_url = f"{base_url}/verify/{r.id}/{integrity_hash}"
    server_signature = make_server_signature(integrity_hash)

    # underwriting payload para PDF (se colunas existirem)
    underwriting = None
    if hasattr(r, "uw_score") or hasattr(r, "uw_decision"):
        underwriting = {
            "uw_score": getattr(r, "uw_score", None),
            "uw_decision": getattr(r, "uw_decision", None),
            "uw_summary": getattr(r, "uw_summary", None),
            "uw_kpis": getattr(r, "uw_kpis", None),
            "uw_factors": getattr(r, "uw_factors", None),
        }

    try:
        pdf_bytes = build_risk_pdf_institutional(
            risk=r,
            analyst_name=u.name,
            generated_at=datetime.utcnow(),
            integrity_hash=integrity_hash,
            server_signature=server_signature,
            verify_url=verify_url,
            underwriting=underwriting,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {type(e).__name__}: {e}")

    log(db, "RISK_PDF_DOWNLOAD", actor=u, entity=None, target_ref=r.id, meta={"entity_id": r.entity_id, "hash": integrity_hash})

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=risk_{r.id}.pdf"},
    )
