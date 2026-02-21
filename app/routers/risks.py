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
    """
    Mantém o teu comportamento atual: cria análise, devolve candidatos/matches mock se aplicável.
    """
    # NOTA: aqui deixo o comportamento mínimo seguro.
    # Se no teu projeto já existe lógica de search (candidates), mantém a tua
    # e só garante que os imports estão certos.
    risk = Risk(
        id=str(uuid.uuid4()),
        entity_id=user.entity_id,
        created_by=user.id,
        full_name=payload.full_name,
        status=RiskStatus.DRAFT,
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)

    return RiskSearchOut(
        risk=RiskOut.model_validate(risk),
        candidates=[],
    )


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
        risk.score = payload.score if hasattr(payload, "score") else getattr(risk, "score", None)
    if hasattr(risk, "justification"):
        risk.justification = getattr(payload, "justification", None) or getattr(risk, "justification", None)
    if hasattr(risk, "matches"):
        risk.matches = getattr(payload, "matches", None) or getattr(risk, "matches", None)

    db.commit()
    db.refresh(risk)
    return RiskOut.model_validate(risk)


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
