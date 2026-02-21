import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_perm, get_current_user
from ..models import Risk, RiskStatus, UserRole
from ..schemas import (
    RiskOut,
    RiskSearchIn,
    RiskSearchOut,
    RiskConfirmIn,
)
from ..pdfs import (
    build_risk_pdf_institutional_pt,
    make_integrity_hash,
    make_server_signature,
)
from ..settings import settings

router = APIRouter(prefix="/risks", tags=["risks"])


def _ensure_scope(user, entity_id: str):
    role_val = getattr(getattr(user, "role", None), "value", getattr(user, "role", None))
    if role_val == "SUPER_ADMIN":
        return
    if not getattr(user, "entity_id", None):
        raise HTTPException(status_code=403, detail="Entity scope missing")
    if user.entity_id != entity_id:
        raise HTTPException(status_code=403, detail="Sem permissão para esta entidade")


@router.post("/search", response_model=RiskSearchOut)
def search_risk(
    payload: RiskSearchIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    FIX DO 500:
    - RiskSearchOut exige disambiguation_required + candidates
    - NÃO devolve 'risk'
    """
    entity_id = payload.entity_id or getattr(user, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    _ensure_scope(user, entity_id)

    full_name = (payload.full_name or "").strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="name is required")

    risk = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        created_by=user.id,
        query_name=full_name,
        query_nationality=payload.nationality,
        status=RiskStatus.DRAFT,
        matches=[],
    )
    db.add(risk)
    db.commit()

    # ✅ resposta 100% compatível com RiskSearchOut
    return RiskSearchOut(disambiguation_required=False, candidates=[])


@router.post("/confirm", response_model=RiskOut)
def confirm_risk(
    payload: RiskConfirmIn,
    db: Session = Depends(get_db),
    user=Depends(require_perm("risk:confirm")),
):
    """
    Endpoint que o frontend chama: POST /risks/confirm
    Suporta NO_MATCH para gerar relatório mesmo sem correspondências.
    """
    entity_id = payload.entity_id or getattr(user, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    _ensure_scope(user, entity_id)

    if not (payload.name or "").strip():
        raise HTTPException(status_code=400, detail="name is required")
    if not (payload.nationality or "").strip():
        raise HTTPException(status_code=400, detail="nationality is required")
    if not (payload.id_number or "").strip():
        raise HTTPException(status_code=400, detail="id_number is required")

    is_no_match = payload.candidate_id == "NO_MATCH"

    risk = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        created_by=user.id,
        query_name=payload.name.strip(),
        query_nationality=payload.nationality.strip(),
        query_bi=payload.id_number.strip() if payload.id_type == "BI" else None,
        query_passport=payload.id_number.strip() if payload.id_type == "PASSPORT" else None,
        status=RiskStatus.DONE,
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
    user=Depends(get_current_user),
):
    q = db.query(Risk)
    role_val = getattr(getattr(user, "role", None), "value", getattr(user, "role", None))
    if role_val != "SUPER_ADMIN":
        q = q.filter(Risk.entity_id == user.entity_id)

    items = q.order_by(Risk.created_at.desc()).limit(200).all()
    return [RiskOut.model_validate(r) for r in items]


@router.get("/{risk_id}", response_model=RiskOut)
def get_risk(
    risk_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    risk = db.query(Risk).filter(Risk.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk não encontrado")

    if user.role != UserRole.SUPER_ADMIN and risk.entity_id != user.entity_id:
        raise HTTPException(status_code=403, detail="Sem permissão para este sector")

    return RiskOut.model_validate(risk)


@router.get("/{risk_id}/pdf")
def get_risk_pdf(
    risk_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_perm("risk:pdf:download")),
):
    risk = db.query(Risk).filter(Risk.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk não encontrado")

    if user.role != UserRole.SUPER_ADMIN and risk.entity_id != user.entity_id:
        raise HTTPException(status_code=403, detail="Sem permissão para este sector")

    generated_at = datetime.now(timezone.utc)
    integrity_hash = make_integrity_hash(risk)
    server_signature = make_server_signature(integrity_hash)
    verify_url = f"{settings.BASE_URL.rstrip('/')}/verify/{risk.id}/{integrity_hash}"

    pdf_bytes = build_risk_pdf_institutional_pt(
        risk=risk,
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
        headers={"Content-Disposition": f'attachment; filename="risk-{risk.id}.pdf"'},
    )
