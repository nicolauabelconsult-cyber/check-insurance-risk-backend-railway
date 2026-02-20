from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import openpyxl


REQUIRED = {
    "PEP": ["full_name", "role", "country", "pep_level", "source"],
    "SANCTIONS": ["full_name", "list_name", "country", "sanction_type", "source"],
    "ADVERSE_MEDIA": ["subject_name", "headline", "media_type", "publication", "publication_date", "source"],
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
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
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
    if not rows:
        return []
    headers = [str(h).strip() for h in rows[0]]
    out = []
    for r in rows[1:]:
        item = {headers[i]: r[i] for i in range(min(len(headers), len(r)))}
        out.append(item)
    return out


def _subject_key(category: str, row: Dict[str, Any]) -> str:
    if category in ("PEP", "SANCTIONS"):
        return (_s(row.get("full_name")) or "").lower().strip()
    if category == "ADVERSE_MEDIA":
        return (_s(row.get("subject_name")) or "").lower().strip()
    return (_s(row.get("entity_name")) or "").lower().strip()


def parse_official(category: str, filename: str, file_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    category = (category or "").upper().strip()
    if category not in REQUIRED:
        raise ValueError("Categoria inválida.")

    name = (filename or "").lower()
    if name.endswith(".csv"):
        rows = _read_csv(file_bytes)
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        rows = _read_xlsx(file_bytes)
    else:
        raise ValueError("Formato inválido. Use CSV ou XLSX.")

    valid: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []

    for idx, row in enumerate(rows, start=2):
        errors = []

        for f in REQUIRED[category]:
            if not _s(row.get(f)):
                errors.append(f"Campo obrigatório em falta: {f}")

        if category == "PEP":
            lvl = _s(row.get("pep_level"))
            if lvl:
                lvl2 = lvl.upper()
                if lvl2 not in ("NATIONAL", "FOREIGN"):
                    errors.append("pep_level inválido (NATIONAL/FOREIGN).")
                row["pep_level"] = lvl2
            row["date_of_birth"] = _parse_date(row.get("date_of_birth"))
            row["start_date"] = _parse_date(row.get("start_date"))
            row["end_date"] = _parse_date(row.get("end_date"))

        if category == "SANCTIONS":
            row["date_of_birth"] = _parse_date(row.get("date_of_birth"))

        if category == "ADVERSE_MEDIA":
            pd = _parse_date(row.get("publication_date"))
            if not pd:
                errors.append("publication_date inválida (use YYYY-MM-DD).")
            else:
                row["publication_date"] = pd

        subj = _subject_key(category, row)
        if not subj:
            errors.append("Nome vazio (não foi possível normalizar subject).")

        if errors:
            invalid.append({"row_number": idx, "errors": errors, "raw": row})
        else:
            keep = REQUIRED[category] + OPTIONAL[category]
            cleaned = {k: row.get(k) for k in keep if _s(row.get(k)) is not None}
            valid.append(cleaned)

    return valid, invalid
