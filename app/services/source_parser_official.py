from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

import openpyxl


REQUIRED = {
    "PEP": ["full_name", "role", "country", "pep_level", "source"],
    "SANCTIONS": ["full_name", "list_name", "country", "sanction_type", "source"],
    "ADVERSE_MEDIA": [
        "subject_name",
        "headline",
        "media_type",
        "publication",
        "publication_date",
        "source",
    ],
    "WATCHLIST": ["entity_name", "country", "regulator", "status", "source"],
}

OPTIONAL = {
    "PEP": ["date_of_birth", "start_date", "end_date", "notes"],
    "SANCTIONS": ["date_of_birth", "reference_id", "notes"],
    "ADVERSE_MEDIA": ["url", "severity", "notes"],
    "WATCHLIST": ["license_number", "notes"],
}


def _s(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        t = v.strip()
        return t if t else None
    return str(v).strip() or None


def _parse_date(v: Any) -> Optional[str]:
    v = _s(v)
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt).date().isoformat()
        except Exception:
            pass
    return None


def _read_csv(file_bytes: bytes) -> List[Dict[str, Any]]:
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(r) for r in reader]


def _read_xlsx(file_bytes: bytes) -> List[Dict[str, Any]]:
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    headers = [str(h).strip() for h in rows[0]]
    data = []
    for r in rows[1:]:
        row = {headers[i]: r[i] for i in range(len(headers))}
        data.append(row)
    return data


def parse_official(category: str, filename: str, file_bytes: bytes):
    category = category.upper().strip()
    if category not in REQUIRED:
        raise ValueError("Categoria inválida.")

    if filename.lower().endswith(".csv"):
        rows = _read_csv(file_bytes)
    elif filename.lower().endswith(".xlsx"):
        rows = _read_xlsx(file_bytes)
    else:
        raise ValueError("Formato inválido. Use CSV ou XLSX.")

    valid = []
    invalid = []

    for idx, row in enumerate(rows, start=2):
        errors = []

        for field in REQUIRED[category]:
            if not _s(row.get(field)):
                errors.append(f"Campo obrigatório em falta: {field}")

        if category == "PEP":
            lvl = _s(row.get("pep_level"))
            if lvl and lvl.upper() not in ("NATIONAL", "FOREIGN"):
                errors.append("pep_level inválido.")
            row["pep_level"] = lvl.upper() if lvl else None

        if category == "ADVERSE_MEDIA":
            row["publication_date"] = _parse_date(row.get("publication_date"))

        if errors:
            invalid.append({"row_number": idx, "errors": errors, "raw": row})
        else:
            keep = REQUIRED[category] + OPTIONAL[category]
            cleaned = {k: row.get(k) for k in keep if _s(row.get(k))}
            valid.append(cleaned)

    return valid, invalid
