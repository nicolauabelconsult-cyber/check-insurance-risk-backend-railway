from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import hashlib

from models import Risk
from core.deps import get_db

router = APIRouter()


@router.get("/verify/{risk_id}/{hash_value}")
def verify_risk(
    risk_id: str,
    hash_value: str,
    db: Session = Depends(get_db),
):

    risk = db.query(Risk).filter(Risk.id == risk_id).first()

    if not risk:
        raise HTTPException(status_code=404, detail="Not found")

    raw = f"{risk.id}{risk.score}{risk.level}{risk.created_at}"
    expected_hash = hashlib.sha256(raw.encode()).hexdigest()

    return {
        "valid": expected_hash == hash_value,
        "risk_id": risk.id,
        "score": risk.score,
        "level": risk.level,
    }
