# risk_service.py
"""
Endpoints de risco usados pelo frontend:
- POST /api/risk/check          -> nova análise de risco
- GET  /api/risk/history/{id}   -> histórico por NIF/passaporte/cartão
- POST /api/risk/{record_id}/confirm -> confirmar entidade escolhida
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, RiskRecord
from auth import get_current_active_user, get_current_admin
from risk_engine import (
    analyze_risk_request,
    get_history_for_identifier,
    confirm_match_and_persist,
)

router = APIRouter(prefix="/risk", tags=["Risk"])


# -----------------------------------------------------------
# 1) Nova análise de risco
# -----------------------------------------------------------

@router.post("/check")
def check_risk(
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Recebe:
    {
      "full_name": "...",
      "nif": "...",              # opcional
      "passport": "...",         # opcional
      "resident_card": "...",    # opcional
      "country": "AO"            # opcional
    }
    """

    full_name = (payload.get("full_name") or "").strip()
    if not full_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O campo 'full_name' é obrigatório.",
        )

    nif = payload.get("nif")
    passport = payload.get("passport")
    resident_card = payload.get("resident_card")
    country = payload.get("country")

    # 1) chamar motor de risco
    result = analyze_risk_request(
        db=db,
        name=full_name,
        nif=nif,
        passport=passport,
        resident_card=resident_card,
        nationality=country,
    )

    # 2) gravar RiskRecord
    record = RiskRecord(
        full_name=full_name,
        nif=nif,
        passport=passport,
        resident_card=resident_card,
        country=country,
        score=int(result["score"]),
        level=result["level"],
        decision="PENDING",
        explanation={"factors": result["factors"]},
        analyst_id=current_user.id,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    # 3) resposta para o frontend
    return {
        "record_id": record.id,
        "score": record.score,
        "level": record.level,
        "decision": record.decision,
        "factors": result["factors"],
        "candidates": result["candidates"],
    }


# -----------------------------------------------------------
# 2) Histórico por identificador (NIF/passaporte/cartão)
# -----------------------------------------------------------

@router.get("/history/{identifier}")
def risk_history(
    identifier: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    records = get_history_for_identifier(db, identifier)

    return [
        {
            "id": r.id,
            "created_at": r.created_at,
            "full_name": r.full_name,
            "score": r.score,
            "level": r.level,
            "decision": r.decision,
        }
        for r in records
    ]


# -----------------------------------------------------------
# 3) Confirmar entidade escolhida (multi-match)
# -----------------------------------------------------------

@router.post("/{record_id}/confirm")
def confirm_risk_match(
    record_id: int,
    data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """
    body:
    {
      "entity_id": 123   # id do NormalizedEntity escolhido
    }
    """
    entity_id = data.get("entity_id")
    if entity_id is None:
        raise HTTPException(400, "O campo 'entity_id' é obrigatório.")

    record = db.query(RiskRecord).filter(RiskRecord.id == record_id).first()
    if not record:
        raise HTTPException(404, "Registo de risco não encontrado.")

    record = confirm_match_and_persist(
        db=db,
        risk_record=record,
        chosen_candidate_id=entity_id,
    )

    return {
        "id": record.id,
        "confirmed_entity_id": record.confirmed_entity_id,
    }
