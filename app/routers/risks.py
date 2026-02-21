# app/routers/risks.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_perm
from app.models import Risk, RiskStatus, UserRole
from app.schemas import (
    RiskOut,
    RiskSearchIn,
    RiskSearchOut,
    CandidateOut,
    RiskConfirmIn,
)

router = APIRouter(prefix="/risks", tags=["risks"])


@router.post("/search", response_model=RiskSearchOut)
def search_risk(
    body: RiskSearchIn,
    db: Session = Depends(get_db),
    u=Depends(get_current_user),
):
    """
    Produção V1:
    - cria Risk em DRAFT
    - devolve candidates (mock por agora) + risk
    Payload alinhado ao frontend: {name, nationality?, entity_id?}
    """
    entity_id = body.entity_id or getattr(u, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

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

    # Motor real ainda não ligado: candidates vazio por agora
    return RiskSearchOut(
        disambiguation_required=False,
        candidates=[],
        risk=RiskOut.model_validate(risk),
    )


@router.post("/confirm", response_model=RiskOut)
def confirm_risk_direct(
    body: RiskConfirmIn,
    db: Session = Depends(get_db),
    u=Depends(require_perm("risks:confirm")),
):
    """
    Endpoint compatível com o frontend (POST /risks/confirm).
    Marca como DONE e grava BI/PASSPORT conforme id_type.
    """
    entity_id = body.entity_id or getattr(u, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    # Scoping: só SUPER_ADMIN pode confirmar para outra entidade
    if u.role != UserRole.SUPER_ADMIN:
        if not getattr(u, "entity_id", None):
            raise HTTPException(status_code=403, detail="Entity scope missing")
        if entity_id != u.entity_id:
            raise HTTPException(status_code=403, detail="Forbidden")

    if body.id_type == "BI":
        q_bi = body.id_number.strip()
        q_pass = None
    else:
        q_bi = None
        q_pass = body.id_number.strip()

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
        score=None,
        summary=None,
    )

    db.add(risk)
    db.commit()
    db.refresh(risk)
    return RiskOut.model_validate(risk)


@router.get("", response_model=list[RiskOut])
def list_risks(
    db: Session = Depends(get_db),
    u=Depends(get_current_user),
):
    q = db.query(Risk)

    # Scoping por entidade (apenas SUPER_ADMIN vê tudo)
    role_val = getattr(getattr(u, "role", None), "value", getattr(u, "role", None))
    if role_val != "SUPER_ADMIN":
        if not getattr(u, "entity_id", None):
            raise HTTPException(status_code=403, detail="Entity scope missing")
        q = q.filter(Risk.entity_id == u.entity_id)

    rows = q.order_by(Risk.created_at.desc()).limit(200).all()
    return [RiskOut.model_validate(r) for r in rows]


@router.get("/{risk_id}", response_model=RiskOut)
def get_risk(
    risk_id: str,
    db: Session = Depends(get_db),
    u=Depends(get_current_user),
):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Risk not found")

    role_val = getattr(getattr(u, "role", None), "value", getattr(u, "role", None))
    if role_val != "SUPER_ADMIN":
        if not getattr(u, "entity_id", None):
            raise HTTPException(status_code=403, detail="Entity scope missing")
        if r.entity_id != u.entity_id:
            raise HTTPException(status_code=403, detail="Forbidden")

    return RiskOut.model_validate(r)
