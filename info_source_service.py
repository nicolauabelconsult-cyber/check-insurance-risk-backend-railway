from datetime import datetime
from typing import IO

from sqlalchemy.orm import Session
from openpyxl import load_workbook
import csv
from io import TextIOWrapper

from app import models
from app.config import settings
from app.utils import normalize_text, normalize_id


def create_info_source(
    db: Session, name: str, source_type: str, description: str | None, user_id: int | None
) -> models.InfoSource:
    src = models.InfoSource(
        name=name,
        source_type=source_type,
        description=description,
        created_by_id=user_id,
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    return src


def _get_risk_weight_for_source_type(source_type: str) -> int:
    return settings.RISK_WEIGHTS.get(source_type.upper(), 40)


def import_csv_entities(
    db: Session,
    source: models.InfoSource,
    file: IO[bytes],
    delimiter: str = ";",
) -> int:
    text_stream = TextIOWrapper(file, encoding="utf-8")
    reader = csv.DictReader(text_stream, delimiter=delimiter)
    count = 0
    for row in reader:
        full_name = row.get("nome") or row.get("name") or ""
        nif = row.get("nif")
        passport = row.get("passaporte") or row.get("passport")
        resident_card = row.get("cartao_residente") or row.get("resident_card")
        country = row.get("pais") or row.get("country")
        position = row.get("cargo") or row.get("role")

        entity = models.NormalizedEntity(
            source_id=source.id,
            source_type=source.source_type,
            source_risk_weight=_get_risk_weight_for_source_type(source.source_type),
            full_name_norm=normalize_text(full_name) or "",
            nif_norm=normalize_id(nif),
            passport_norm=normalize_id(passport),
            resident_card_norm=normalize_id(resident_card),
            country_code=(country or None),
            role_or_position=position,
            extra_data=row,
        )
        db.add(entity)
        count += 1

    db.commit()
    source.record_count = count
    source.last_import_at = datetime.utcnow()
    db.add(source)
    db.commit()
    return count


def import_xlsx_entities(
    db: Session,
    source: models.InfoSource,
    file: IO[bytes],
) -> int:
    wb = load_workbook(file, read_only=True)
    ws = wb.active
    rows = list(ws.rows)
    if not rows:
        return 0
    headers = [str(cell.value).strip().lower() for cell in rows[0]]
    count = 0
    for row in rows[1:]:
        data = {headers[i]: (row[i].value if i < len(row) else None) for i in range(len(headers))}
        full_name = data.get("nome") or data.get("name") or ""
        nif = data.get("nif")
        passport = data.get("passaporte") or data.get("passport")
        resident_card = data.get("cartao_residente") or data.get("resident_card")
        country = data.get("pais") or data.get("country")
        position = data.get("cargo") or data.get("role")

        entity = models.NormalizedEntity(
            source_id=source.id,
            source_type=source.source_type,
            source_risk_weight=_get_risk_weight_for_source_type(source.source_type),
            full_name_norm=normalize_text(full_name) or "",
            nif_norm=normalize_id(nif),
            passport_norm=normalize_id(passport),
            resident_card_norm=normalize_id(resident_card),
            country_code=(country or None),
            role_or_position=position,
            extra_data=data,
        )
        db.add(entity)
        count += 1
    db.commit()
    source.record_count = count
    source.last_import_at = datetime.utcnow()
    db.add(source)
    db.commit()
    return count
