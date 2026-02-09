# app/routers/risks.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import traceback

from ..db import get_db
from ..deps import require_perm
from ..models import Risk, UserRole
from ..schemas import RiskOut

router = APIRouter(prefix="/risks", tags=["risks"])

@router.get("", response_model=list[RiskOut])
def list_risks(db: Session = Depends(get_db), u=Depends(require_perm("risk:read"))):
    try:
        q = db.query(Risk)

        if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
            q = q.filter(Risk.entity_id == u.entity_id)

        rows = q.order_by(Risk.id.desc()).all()

        return [
            RiskOut(
                id=str(getattr(r, "id")),
                entity_id=getattr(r, "entity_id", None),

                # ✅ isto evita o crash
                name=getattr(r, "name", None),
                bi=getattr(r, "bi", None),
                passport=getattr(r, "passport", None),
                nationality=getattr(r, "nationality", None),

                score=getattr(r, "score", None),
                summary=getattr(r, "summary", None),
                matches=getattr(r, "matches", []) or [],
                status=getattr(r, "status", "UNKNOWN"),
            )
            for r in rows
        ]

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
