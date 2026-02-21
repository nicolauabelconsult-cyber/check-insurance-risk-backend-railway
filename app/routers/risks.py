import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_perm, get_current_user
from app.models import Risk, RiskStatus, UserRole
from app.schemas import RiskOut, RiskSearchIn, RiskSearchOut, RiskConfirmIn
from app.pdfs import build_risk_pdf_institutional_pt, make_integrity_hash, make_server_signature
from app.settings import settings

router = APIRouter(prefix="/risks", tags=["risks"])


def _ensure_scope(user, entity_id: str):
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
    entity_id = payload.entity_id or getattr(user, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    _ensure_scope(user, entity_id)

    risk = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        created_by=user.id,
        query_name=payload.full_name,
        query_nationality=payload.nationality,
        status=RiskStatus.DRAFT,
        matches=[],
        score=None,
        summary=None,
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)

    # V1: candidatos ainda vazio
    return RiskSearchOut(disambiguation_required=False, candidates=[])


@router.post("/confirm", response_model=RiskOut)
def confirm_no_match_or_candidate(
    payload: RiskConfirmIn,
    db: Session = Depends(get_db),
    user=Depends(require_perm("risk:confirm")),
):
    """
    Confirma direto (inclui NO_MATCH) e grava DONE.
    O frontend chama este endpoint.
    """
    entity_id = payload.entity_id or getattr(user, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    _ensure_scope(user, entity_id)

    is_no_match = payload.candidate_id == "NO_MATCH"

    r = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        created_by=user.id,
        query_name=payload.name,
        query_nationality=payload.nationality,
        query_bi=(payload.id_number if payload.id_type == "BI" else None),
        query_passport=(payload.id_number if payload.id_type == "PASSPORT" else None),
        status=RiskStatus.DONE,
        matches=[],
        score="0" if is_no_match else None,
        summary="Sem correspondência nas fontes disponíveis." if is_no_match else None,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return RiskOut.model_validate(r)


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

    # Nota: a tua Settings tem PDF_SECRET_KEY, mas a função usa JWT_SECRET se não houver outro
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
