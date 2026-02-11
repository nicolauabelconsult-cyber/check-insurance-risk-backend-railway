from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_perm
from ..models import Risk, RiskStatus, UserRole
from ..schemas import RiskOut, RiskSearchIn, RiskSearchOut, CandidateOut, RiskConfirmIn

router = APIRouter(prefix="/risks", tags=["risks"])

def _resolve_entity_id(u, requested: str | None) -> str:
    # SUPER/ADMIN podem escolher
    if u.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        if not requested:
            raise HTTPException(status_code=400, detail="entity_id required for admin")
        return requested

    # clientes: scoping perfeito
    if not u.entity_id:
        raise HTTPException(status_code=400, detail="user has no entity_id")
    return u.entity_id


@router.post("/search", response_model=RiskSearchOut)
def search_risks(data: RiskSearchIn, db: Session = Depends(get_db), u=Depends(require_perm("risk:create"))):
    entity_id = _resolve_entity_id(u, data.entity_id)

    # aqui já não há risco de pesquisar fora da entidade para clientes
    name = (data.name or "").strip().lower()
    nat = (data.nationality or "").strip().lower()

    # ... (o teu mock CANDIDATES igual)
    # return {"disambiguation_required": ..., "candidates": ...}


@router.post("/confirm", response_model=RiskOut)
def confirm_risk(data: RiskConfirmIn, db: Session = Depends(get_db), u=Depends(require_perm("risk:confirm"))):
    entity_id = _resolve_entity_id(u, data.entity_id)

    # ... valida candidato + doc (igual)

    r = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,          # ✅ aqui está o scoping real
        query_name=data.name,
        query_nationality=data.nationality,
        query_bi=data.id_number if data.id_type == "BI" else None,
        query_passport=data.id_number if data.id_type == "PASSPORT" else None,
        score=score,
        summary=summary,
        matches=[...],
        status=RiskStatus.DONE,
        created_by=u.id,
    )

    db.add(r)
    db.commit()
    return _risk_out(r)
