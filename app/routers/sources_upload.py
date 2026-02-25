from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_perm, ensure_entity_scope
from app.models import Source
from app.models_source_records import SourceRecord
from app.services.source_parser_official import parse_official

# ✅ TEM de se chamar "router"
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

    # 🔒 Multi-tenant scope
    ensure_entity_scope(user, src.entity_id)

    category = (getattr(src, "category", None) or "").upper().strip()
    if category not in ("PEP", "SANCTIONS", "ADVERSE_MEDIA", "WATCHLIST", "INSURANCE"):
        raise HTTPException(status_code=400, detail="Fonte sem categoria válida.")

    # Sector = tenant (na tua V1)
    entity_id = getattr(src, "entity_id", None) or getattr(src, "sector", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="Fonte sem entity_id/sector.")

    content = file.file.read()

    # =========================
    # INSURANCE (Seguros)
    # =========================
    if category == "INSURANCE":
        from app.services.insurance_excel_import import import_insurance_workbook
        # reimport limpo por fonte em underwriting tables + SourceRecord
        db.query(SourceRecord).filter(SourceRecord.source_id == str(src.id)).delete()
        result = import_insurance_workbook(
            db,
            entity_id=str(entity_id),
            source_name=str(src.name),
            source_ref=str(src.id),  # amarra ao source para reimport seguro
            filename=file.filename,
            content=content,
        )

        # Criar SourceRecord mínimos para permitir match por nome via /risks/search
        # (usamos policies como referência principal)
        inserted_policy_names = set()
        try:
            # best-effort: carregar as policies inseridas desta fonte e criar subject_name
            from app.models import InsurancePolicy as UWPolicy
            rows = (
                db.query(UWPolicy)
                .filter(UWPolicy.entity_id == str(entity_id), UWPolicy.source_ref == str(src.id))
                .limit(500)
                .all()
            )
            now = datetime.utcnow()
            for row in rows or []:
                subj = (getattr(row, "subject_full_name", None) or "").lower().strip()
                if not subj or subj in inserted_policy_names:
                    continue
                inserted_policy_names.add(subj)
                db.add(
                    SourceRecord(
                        entity_id=str(entity_id),
                        source_id=str(src.id),
                        category="INSURANCE",
                        subject_name=subj,
                        country=None,
                        raw={
                            "full_name": getattr(row, "subject_full_name", None),
                            "id_number": getattr(row, "subject_bi", None) or getattr(row, "subject_passport", None),
                            "doc_type": "BI" if getattr(row, "subject_bi", None) else ("PASSPORT" if getattr(row, "subject_passport", None) else None),
                            "product_type": getattr(row, "product_type", None),
                            "policy_number": getattr(row, "policy_number", None),
                        },
                        created_at=now,
                    )
                )
            db.commit()
        except Exception:
            db.commit()

        return {
            "source_id": str(src.id),
            "category": category,
            "imported": sum((result.get("inserted") or {}).values()),
            "details": result,
        }

    try:
        valid, invalid = parse_official(category, file.filename, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # reimport limpo por fonte
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
                source_id=str(src.id),  # string, porque sources.id é varchar
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
