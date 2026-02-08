# app/routers/risks.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import ProgrammingError

from ..db import get_db
from ..deps import require_perm
from ..models import Risk, UserRole
from ..schemas import RiskOut

router = APIRouter(prefix="/risks", tags=["risks"])


@router.get("", response_model=list[RiskOut])
def list_risks(db: Session = Depends(get_db), u=Depends(require_perm("risk:read"))):
    q = db.query(Risk)

    if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        q = q.filter(Risk.entity_id == u.entity_id)

    try:
        rows = q.order_by(Risk.created_at.desc()).all()
    except ProgrammingError:
        # fallback: se created_at não existir ainda na BD
        rows = q.order_by(Risk.id.desc()).all()

    return [
        RiskOut(
            id=r.id,
            entity_id=r.entity_id,
            name=r.name,
            bi=r.bi,
            passport=r.passport,
            nationality=r.nationality,
            score=r.score,
            summary=r.summary,
            matches=r.matches or [],
            status=r.status,
        )
        for r in rows
    ]
