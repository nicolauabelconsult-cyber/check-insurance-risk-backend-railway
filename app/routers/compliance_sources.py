from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import require_perm
from app.models_compliance import ComplianceRecord
from datetime import datetime

router = APIRouter(prefix="/compliance", tags=["compliance"])

@router.post("/bulk")
def bulk_import(payload: dict, db: Session = Depends(get_db), u=Depends(require_perm("compliance:write"))):
    """
    payload exemplo:
    {
      "entity_id": "...",
      "category": "PEP",
      "source_system": "INTERNAL",
      "records": [{...},{...}]
    }
    """
    entity_id = payload.get("entity_id")
    category = payload.get("category")
    source_system = payload.get("source_system")
    records = payload.get("records") or []

    if not entity_id or not category or not source_system:
        raise HTTPException(400, "entity_id/category/source_system required")

    rows = []
    for r in records:
        rows.append(
            ComplianceRecord(
                entity_id=entity_id,
                category=category,
                source_system=source_system,
                source_ref=r.get("source_ref"),
                full_name=r.get("full_name") or r.get("name") or "",
                nationality=r.get("nationality"),
                dob=r.get("dob"),
                id_number=r.get("id_number"),
                aliases=r.get("aliases"),
                risk_level=r.get("risk_level"),
                raw=r,
                created_at=datetime.utcnow(),
            )
        )

    db.add_all(rows)
    db.commit()
    return {"inserted": len(rows)}
