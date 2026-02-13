from __future__ import annotations

from typing import Any
import re

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.compliance_models import PepRecord


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _name_similarity(a: str, b: str) -> float:
    ta = set(_norm(a).split())
    tb = set(_norm(b).split())
    if not ta or not tb:
        return 0.0
    inter = len(ta.intersection(tb))
    denom = max(len(ta), len(tb))
    return inter / denom


def pep_match(
    db: Session,
    entity_id: str,
    full_name: str | None,
    bi: str | None,
    passport: str | None,
    min_name_score: float = 0.70,
) -> list[dict[str, Any]]:

    results: list[dict[str, Any]] = []

    q = db.query(PepRecord).filter(PepRecord.entity_id == entity_id)

    exact_filters = []
    if bi:
        exact_filters.append(PepRecord.bi == bi)
    if passport:
        exact_filters.append(PepRecord.passport == passport)

    exact_hits = []
    if exact_filters:
        exact_hits = q.filter(or_(*exact_filters)).all()

    # Documento exact match
    for r in exact_hits:
        results.append(
            {
                "type": "PEP",
                "source": r.source_name,
                "match": True,
                "confidence": 0.98,
                "note": f"PEP confirmado por documento. Cargo: {r.pep_role or '-'}; País: {r.country or '-'}",
                "pep_category": r.pep_category,
                "pep_role": r.pep_role,
                "country": r.country,
                "risk_level": r.risk_level,
                "record_id": r.id,
                "source_ref": r.source_ref,
            }
        )

    # Nome match
    if full_name:
        name_hits = q.all()
        for r in name_hits:
            score = _name_similarity(full_name, r.full_name or "")
            if r.aka:
                score = max(score, _name_similarity(full_name, r.aka))

            if score >= min_name_score:
                if any(x["record_id"] == r.id for x in results):
                    continue

                results.append(
                    {
                        "type": "PEP",
                        "source": r.source_name,
                        "match": True,
                        "confidence": round(score, 2),
                        "note": f"Possível PEP por similaridade de nome. Cargo: {r.pep_role or '-'}; País: {r.country or '-'}",
                        "pep_category": r.pep_category,
                        "pep_role": r.pep_role,
                        "country": r.country,
                        "risk_level": r.risk_level,
                        "record_id": r.id,
                        "source_ref": r.source_ref,
                    }
                )

    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results[:20]
