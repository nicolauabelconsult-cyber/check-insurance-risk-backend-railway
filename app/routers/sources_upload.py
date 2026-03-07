from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import ensure_entity_scope, require_perm
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

    # Read bytes safely
    try:
        content = file.file.read()
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    if not content:
        raise HTTPException(status_code=400, detail="Ficheiro vazio.")

    # =========================
    # INSURANCE (Seguros)
    # =========================
    if category == "INSURANCE":
        from app.services.insurance_excel_import import import_insurance_workbook

        # reimport limpo por fonte em underwriting tables + SourceRecord
        db.query(SourceRecord).filter(SourceRecord.source_id == str(src.id)).delete()

        try:
            result = import_insurance_workbook(
                db,
                entity_id=str(entity_id),
                source_name=str(src.name),
                source_ref=str(src.id),  # amarra ao source para reimport seguro
                filename=file.filename,
                content=content,
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Erro no import de Seguros: {e}")

        # Criar SourceRecord mínimos para permitir match por nome via /risks/search
        inserted_policy_names = set()
        try:
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
                            "id_number": getattr(row, "subject_bi", None)
                            or getattr(row, "subject_passport", None),
                            "doc_type": "BI"
                            if getattr(row, "subject_bi", None)
                            else (
                                "PASSPORT" if getattr(row, "subject_passport", None) else None
                            ),
                            "product_type": getattr(row, "product_type", None),
                            "policy_number": getattr(row, "policy_number", None),
                        },
                        created_at=now,
                    )
                )
            db.commit()
        except Exception:
            # best-effort: não falhar o upload se só o SourceRecord falhar
            db.commit()

        return {
            "source_id": str(src.id),
            "category": category,
            "imported": sum((result.get("inserted") or {}).values()),
            "details": result,
        }

    # =========================
    # OFFICIAL LISTS (PEP/Sanctions/etc.)
    # =========================
    try:
        valid, invalid = parse_official(category, file.filename, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro no import da fonte: {e}")

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
                source_id=str(src.id),
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
