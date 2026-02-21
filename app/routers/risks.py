# app/routers/risks.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_perm
from app.models import Risk, RiskStatus, UserRole
from app.pdfs import (
    build_risk_pdf_institutional_pt,
    make_integrity_hash,
    make_server_signature,
)
from app.settings import settings
from app.schemas import RiskOut, RiskSearchIn, RiskSearchOut, RiskConfirmIn

router = APIRouter(prefix="/risks", tags=["risks"])


def _ensure_scope(u, entity_id: str):
    # SUPER_ADMIN pode operar em qualquer entidade
    if u.role == UserRole.SUPER_ADMIN:
        return
    if not getattr(u, "entity_id", None):
        raise HTTPException(status_code=403, detail="Entity scope missing")
    if u.entity_id != entity_id:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/search", response_model=RiskSearchOut)
def search_risk(
    body: RiskSearchIn,
    db: Session = Depends(get_db),
    u=Depends(require_perm("risk:create")),
):
    """
    Produção V1:
    - cria Risk em DRAFT (persistido)
    - devolve candidates vazio por agora + risk
    """
    entity_id = body.entity_id or getattr(u, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    _ensure_scope(u, entity_id)

    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="name is required")

    risk = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        created_by=u.id,
        status=RiskStatus.DRAFT,
        query_name=body.name.strip(),
        query_nationality=(body.nationality.strip() if body.nationality else None),
        matches=[],
        score=None,
        summary=None,
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)

    return RiskSearchOut(
        disambiguation_required=False,
        candidates=[],
        risk=RiskOut.model_validate(risk),
    )


@router.post("/confirm", response_model=RiskOut)
def confirm_risk_direct(
    body: RiskConfirmIn,
    db: Session = Depends(get_db),
    u=Depends(require_perm("risk:confirm")),
):
    """
    Produção V1:
    - Se candidate_id = "NO_MATCH": grava DONE com score=0 e summary "Sem correspondência"
    - Mantém tudo persistido e pronto para PDF
    """
    entity_id = body.entity_id or getattr(u, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    _ensure_scope(u, entity_id)

    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="name is required")
    if not body.nationality or not body.nationality.strip():
        raise HTTPException(status_code=400, detail="nationality is required")
    if not body.id_number or not body.id_number.strip():
        raise HTTPException(status_code=400, detail="id_number is required")

    q_bi = body.id_number.strip() if body.id_type == "BI" else None
    q_pass = body.id_number.strip() if body.id_type == "PASSPORT" else None

    is_no_match = body.candidate_id == "NO_MATCH"

    risk = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        created_by=u.id,
        status=RiskStatus.DONE,
        query_name=body.name.strip(),
        query_nationality=body.nationality.strip(),
        query_bi=q_bi,
        query_passport=q_pass,
        matches=[],
        score="0" if is_no_match else None,
        summary="Sem correspondência nas fontes disponíveis." if is_no_match else None,
    )

    db.add(risk)
    db.commit()
    db.refresh(risk)
    return RiskOut.model_validate(risk)


@router.get("", response_model=list[RiskOut])
def list_risks(
    db: Session = Depends(get_db),
    u=Depends(require_perm("risk:read")),
):
    q = db.query(Risk)

    if u.role != UserRole.SUPER_ADMIN:
        if not getattr(u, "entity_id", None):
            raise HTTPException(status_code=403, detail="Entity scope missing")
        q = q.filter(Risk.entity_id == u.entity_id)

    rows = q.order_by(Risk.created_at.desc()).limit(200).all()
    return [RiskOut.model_validate(r) for r in rows]


@router.get("/{risk_id}", response_model=RiskOut)
def get_risk(
    risk_id: str,
    db: Session = Depends(get_db),
    u=Depends(require_perm("risk:read")),
):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Risk não encontrado")

    _ensure_scope(u, r.entity_id)
    return RiskOut.model_validate(r)


@router.get("/{risk_id}/pdf")
def get_risk_pdf(
    risk_id: str,
    db: Session = Depends(get_db),
    u=Depends(require_perm("risk:read")),
):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Risk não encontrado")

    _ensure_scope(u, r.entity_id)

    generated_at = datetime.now(timezone.utc)
    integrity_hash = make_integrity_hash(r)
    server_signature = make_server_signature(integrity_hash)
    verify_url = f"{settings.BASE_URL.rstrip('/')}/verify/{r.id}/{integrity_hash}"

    pdf_bytes = build_risk_pdf_institutional_pt(
        risk=r,
        analyst_name=getattr(u, "name", "Analista"),
        generated_at=generated_at,
        integrity_hash=integrity_hash,
        server_signature=server_signature,
        verify_url=verify_url,
        underwriting_by_product=None,
        compliance_by_category=None,
    )

    filename = f"risk_{r.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
