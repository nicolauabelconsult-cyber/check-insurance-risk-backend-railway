# app/routers/risks.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_perm
from app.models import Risk, RiskStatus, UserRole
from app.schemas import RiskOut, RiskSearchIn, RiskSearchOut, RiskConfirmIn
from app.pdfs import build_risk_pdf_institutional_pt, make_integrity_hash, make_server_signature
from app.settings import settings

router = APIRouter(prefix="/risks", tags=["risks"])


def _ensure_scope(user, entity_id: str) -> None:
    """SUPER_ADMIN vê tudo; os outros só podem operar na sua entity_id."""
    if user.role == UserRole.SUPER_ADMIN:
        return
    if not getattr(user, "entity_id", None):
        raise HTTPException(status_code=403, detail="Entity scope missing")
    if user.entity_id != entity_id:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/search", response_model=RiskSearchOut)
def search_risk(
    payload: RiskSearchIn,
    db: Session = Depends(get_db),
    user=Depends(require_perm("risk:create")),
):
    """
    Produção V1:
    - cria um Risk em DRAFT (persistido)
    - devolve candidates (por agora vazio)
    """
    entity_id = payload.entity_id or getattr(user, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    _ensure_scope(user, entity_id)

    name = (payload.full_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    risk = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        created_by=user.id,
        status=RiskStatus.DRAFT,
        query_name=name,
        query_nationality=(payload.nationality.strip() if payload.nationality else None),
        matches=[],
        score=None,
        summary=None,
    )
    db.add(risk)
    db.commit()

    # Schema atual do teu backend: RiskSearchOut tem só (disambiguation_required, candidates)
    return RiskSearchOut(disambiguation_required=False, candidates=[])


@router.post("/confirm", response_model=RiskOut)
def confirm_risk(
    payload: RiskConfirmIn,
    db: Session = Depends(get_db),
    user=Depends(require_perm("risk:confirm")),
):
    """
    Compatível com o frontend:
    - POST /risks/confirm
    - suporta candidate_id="NO_MATCH" e grava DONE
    """
    entity_id = payload.entity_id or getattr(user, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    _ensure_scope(user, entity_id)

    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    if not payload.nationality.strip():
        raise HTTPException(status_code=400, detail="nationality is required")
    if not payload.id_number.strip():
        raise HTTPException(status_code=400, detail="id_number is required")

    is_no_match = payload.candidate_id == "NO_MATCH"

    risk = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        created_by=user.id,
        status=RiskStatus.DONE,
        query_name=payload.name.strip(),
        query_nationality=payload.nationality.strip(),
        query_bi=(payload.id_number.strip() if payload.id_type == "BI" else None),
        query_passport=(payload.id_number.strip() if payload.id_type == "PASSPORT" else None),
        matches=[],
        score="0" if is_no_match else None,
        summary="Sem correspondência nas fontes disponíveis." if is_no_match else None,
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)
    return RiskOut.model_validate(risk)


@router.get("/{risk_id}", response_model=RiskOut)
def get_risk(
    risk_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_perm("risk:read")),
):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Risk não encontrado")

    _ensure_scope(user, r.entity_id)
    return RiskOut.model_validate(r)


@router.get("/{risk_id}/pdf")
def get_risk_pdf(
    risk_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_perm("risk:pdf:download")),
):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Risk não encontrado")

    _ensure_scope(user, r.entity_id)

    generated_at = datetime.now(timezone.utc)
    integrity_hash = make_integrity_hash(r)
    server_signature = make_server_signature(integrity_hash)
    verify_url = f"{settings.BASE_URL.rstrip('/')}/verify/{r.id}/{integrity_hash}"

    pdf_bytes = build_risk_pdf_institutional_pt(
        risk=r,
        analyst_name=getattr(user, "name", "Analista"),
        generated_at=generated_at,
        integrity_hash=integrity_hash,
        server_signature=server_signature,
        verify_url=verify_url,
        underwriting_by_product=None,
        compliance_by_category=None,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="risk-{r.id}.pdf"'},
    )
