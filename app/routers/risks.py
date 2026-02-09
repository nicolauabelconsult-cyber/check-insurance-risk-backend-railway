# app/routers/risks.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_perm
from ..models import Risk, UserRole
from ..schemas import RiskOut

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

            # ✅ MAPA CERTO (vem dos campos query_*)
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
