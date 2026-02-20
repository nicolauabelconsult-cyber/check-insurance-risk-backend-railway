from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.auth import require_perm
from app.models import Source
from app.models_source_records import SourceRecord
from app.services.source_parser_official import parse_official

router = APIRouter()


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

    category = src.category.upper()

    content = file.file.read()
    valid, invalid = parse_official(category, file.filename, content)

    db.query(SourceRecord).filter(SourceRecord.source_id == src.id).delete()

    for r in valid:
        if category in ("PEP", "SANCTIONS"):
            subject = r.get("full_name", "").lower().strip()
        elif category == "ADVERSE_MEDIA":
            subject = r.get("subject_name", "").lower().strip()
        else:
            subject = r.get("entity_name", "").lower().strip()

        record = SourceRecord(
            entity_id=src.entity_id,
            source_id=src.id,
            category=category,
            subject_name=subject,
            country=r.get("country"),
            raw=r,
            created_at=datetime.utcnow(),
        )
        db.add(record)

    db.commit()

    return {
        "imported": len(valid),
        "invalid": len(invalid),
        "invalid_rows": invalid[:20],
    }
