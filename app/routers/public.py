from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Risk
from app.pdfs import make_integrity_hash


router = APIRouter(tags=["public"])


@router.get("/verify/{risk_id}/{hash_value}")
def verify_risk(risk_id: str, hash_value: str, db: Session = Depends(get_db)):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Not found")

    expected = make_integrity_hash(r)
    return {
        "valid": expected == hash_value,
        "risk_id": r.id,
        "entity_id": r.entity_id,
        "score": r.score,
        "status": r.status.value if hasattr(r.status, "value") else str(r.status),
    }
