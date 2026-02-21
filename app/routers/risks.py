import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_perm, get_current_user
from ..models import Risk, RiskStatus, UserRole
from ..schemas import (
    RiskOut,
    RiskSearchIn,
    RiskSearchOut,
    CandidateOut,
    RiskConfirmIn,
)

router = APIRouter(prefix="/risks", tags=["risks"])


@router.post("/search", response_model=RiskSearchOut)
def search_risk(
    payload: RiskSearchIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Cria uma análise (Risk) e devolve o objeto + candidatos (vazio por agora)."""
    entity_id = payload.entity_id or getattr(user, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    risk = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        created_by=user.id,
        query_name=payload.full_name,
        query_nationality=payload.nationality,
        status=RiskStatus.DRAFT,
        matches=[],
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)

    return RiskSearchOut(
        risk=RiskOut.model_validate(risk),
        disambiguation_required=False,
        candidates=[],
    )


@router.post("/confirm", response_model=RiskOut)
def confirm_risk_direct(
    payload: RiskConfirmIn,
    db: Session = Depends(get_db),
    user=Depends(require_perm("risks:confirm")),
):
    """
    Endpoint compatível com o frontend (POST /risks/confirm).
    Cria um Risk já CONFIRMED. Mantém RBAC via require_perm.
    """
    entity_id = payload.entity_id or getattr(user, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    risk = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        created_by=user.id,
        query_name=payload.name,
        query_nationality=payload.nationality,
        status=RiskStatus.CONFIRMED,
        matches=[],
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)

    return RiskOut.model_validate(risk)


@router.post("/{risk_id}/confirm", response_model=RiskOut)
def confirm_risk(
    risk_id: str,
    payload: RiskConfirmIn,
    db: Session = Depends(get_db),
    user=Depends(require_perm("risks:confirm")),
):
    """
    Confirma o risco (mantém RBAC). Aqui é onde depois ligamos ao motor real.
    """
    risk = db.query(Risk).filter(Risk.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk não encontrado")

    # Scoping: ADMIN/CLIENT só podem operar no seu entity_id
    if user.role != UserRole.SUPER_ADMIN and risk.entity_id != user.entity_id:
        raise HTTPException(status_code=403, detail="Sem permissão para este sector")

    risk.status = RiskStatus.CONFIRMED

    # Mantém os campos do teu modelo (ajusta se existirem no teu Risk)
    if hasattr(risk, "score"):
        risk.score = getattr(payload, "score", None) or getattr(risk, "score", None)
    if hasattr(risk, "justification"):
        risk.justification = getattr(payload, "justification", None) or getattr(risk, "justification", None)
    if hasattr(risk, "matches"):
        risk.matches = getattr(payload, "matches", None) or getattr(risk, "matches", None)

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
