from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_perm
from ..models import Source
from ..models_source_records import SourceRecord
from ..services.source_parser_official import parse_official

router = APIRouter(tags=["sources"])


@router.post("/sources/{source_id}/upload")
def upload_source_file(
    source_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(require_perm("sources:update")),
):
    src = db.query(Source).filter(Source.id == source_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Fonte não encontrada")

    category = (getattr(src, "category", None) or "").upper().strip()
    if category not in ("PEP", "SANCTIONS", "ADVERSE_MEDIA", "WATCHLIST"):
        raise HTTPException(status_code=400, detail="Fonte sem categoria válida.")

    entity_id = getattr(src, "entity_id", None) or getattr(src, "sector", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="Fonte sem entity_id/sector.")

    content = file.file.read()
    try:
        valid, invalid = parse_official(category, file.filename, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.query(SourceRecord).filter(SourceRecord.source_id == str(src.id)).delete()

    now = datetime.utcnow()
    for r in valid:
        if category in ("PEP", "SANCTIONS"):
            subject = (r.get("full_name") or "").lower().strip()
        elif category == "ADVERSE_MEDIA":
            subject = (r.get("subject_name") or "").lower().strip()
        else:
            subject = (r.get("entity_name") or "").lower().strip()

        db.add(
            SourceRecord(
                entity_id=str(entity_id),
                source_id=str(src.id),  # String, porque sources.id é VARCHAR
                category=category,
                subject_name=subject,
                country=r.get("country"),
                raw=r,
                created_at=now,
            )
        )

    db.commit()

    return {
        "source_id": str(src.id),
        "category": category,
        "imported": len(valid),
        "invalid": len(invalid),
        "invalid_rows": invalid[:20],
    }
