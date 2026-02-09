from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from ..db import get_db
from ..deps import require_perm, get_current_user
from ..models import Risk, UserRole, RiskStatus
from ..schemas import RiskOut, RiskCreate

router = APIRouter(prefix="/risks", tags=["risks"])


@router.get("/", response_model=list[RiskOut])
def list_risks(db: Session = Depends(get_db), u=Depends(require_perm("risk:read"))):
    q = db.query(Risk)

    if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        q = q.filter(Risk.entity_id == u.entity_id)

    rows = q.order_by(Risk.created_at.desc()).all()

    return [
        RiskOut(
            id=r.id,
            entity_id=r.entity_id,
            # ✅ MAPA CERTO (model tem query_*)
            name=r.query_name,
            bi=r.query_bi,
            passport=r.query_passport,
            nationality=r.query_nationality,
            score=r.score,
            summary=r.summary,
            matches=r.matches or [],
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
        )
        for r in rows
    ]


@router.get("/{risk_id}", response_model=RiskOut)
def get_risk(risk_id: str, db: Session = Depends(get_db), u=Depends(require_perm("risk:read"))):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Not found")

    if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN) and r.entity_id != u.entity_id:
        raise HTTPException(status_code=403, detail="Forbidden")

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


@router.post("/", response_model=RiskOut)
def create_risk(payload: RiskCreate, db: Session = Depends(get_db), u=Depends(require_perm("risk:create"))):
    # ✅ regra: entity_id é obrigatório (como já tinhas)
    entity_id = payload.entity_id or u.entity_id
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    r = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        query_name=payload.name,
        query_bi=payload.bi,
        query_passport=payload.passport,
        query_nationality=payload.nationality,
        score="LOW",
        summary="Resultado gerado (mock). Pronto para ligar a fontes reais.",
        matches=[],
        status=RiskStatus.DONE,
        created_by=u.id,
    )
    db.add(r)
    db.commit()
    db.refresh(r)

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
