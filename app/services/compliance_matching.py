from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.compliance_models import PepRecord


def _norm(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    # remove pontuação básica para aproximar nomes
    s = re.sub(r"[^\w\s]", "", s)
    return s


def _name_similarity(a: str, b: str) -> float:
    """
    Similaridade simples (0..1) por tokens.
    Banco-ready no MVP: determinístico, rápido e explicável.
    Depois pode trocar por RapidFuzz / trigram / embeddings.
    """
    a = _norm(a)
    b = _norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    ta = set(a.split())
    tb = set(b.split())
    if not ta or not tb:
        return 0.0

    inter = len(ta.intersection(tb))
    union = len(ta.union(tb))
    return inter / union


def pep_match(
    db: Session,
    entity_id: str,
    full_name: str,
    bi: Optional[str] = None,
    passport: Optional[str] = None,
    min_score: int = 65,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Matching PEP (simples e evolutivo):
    - Prioridade 1: BI exact (match_score 100)
    - Prioridade 2: Passaporte exact (match_score 98)
    - Prioridade 3: Nome (similaridade por tokens -> score 0..100)

    Output já no formato "risk.matches" para o PDF e auditoria.
    """
    n_bi = _norm(bi)
    n_pass = _norm(passport)
    q_name = _norm(full_name)

    hits: List[Dict[str, Any]] = []

    # 1) BI exact
    if n_bi:
        rows = (
            db.query(PepRecord)
            .filter(PepRecord.entity_id == entity_id)
            .filter(PepRecord.bi.isnot(None))
            .all()
        )
        for r in rows:
            if _norm(r.bi) == n_bi:
                hits.append(_pep_to_match(r, confidence=1.00, match_score=100, reason="BI exact"))
                if len(hits) >= limit:
                    return hits

    # 2) Passaporte exact
    if n_pass:
        rows = (
            db.query(PepRecord)
            .filter(PepRecord.entity_id == entity_id)
            .filter(PepRecord.passport.isnot(None))
            .all()
        )
        for r in rows:
            if _norm(r.passport) == n_pass:
                hits.append(_pep_to_match(r, confidence=0.98, match_score=98, reason="Passaporte exact"))
                if len(hits) >= limit:
                    return hits

    # 3) Nome aproximado
    # Para MVP: consulta por entity + (full_name not null) e filtra em python
    # Evolução: usar trigram index, full-text, rapidfuzz, etc.
    rows = (
        db.query(PepRecord)
        .filter(PepRecord.entity_id == entity_id)
        .filter(PepRecord.full_name.isnot(None))
        .limit(500)  # proteção
        .all()
    )

    scored = []
    for r in rows:
        sim = _name_similarity(q_name, r.full_name or "")
        score = int(sim * 100)
        if score >= min_score:
            scored.append((score, sim, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    for score, sim, r in scored[: max(0, limit - len(hits))]:
        # confiança: mantemos consistente e explicável
        confidence = round(sim, 2)
        hits.append(_pep_to_match(r, confidence=confidence, match_score=score, reason="Nome aproximado"))

    return hits


def _pep_to_match(
    r: PepRecord,
    confidence: float,
    match_score: int,
    reason: str,
) -> Dict[str, Any]:
    """
    Formato padronizado para risk.matches (já pronto para PDF institucional).
    """
    return {
        "type": "PEP",
        "source": r.source_name or "PEP_INTERNAL",
        "match": True,
        "confidence": confidence,        # 0..1
        "match_score": match_score,      # 0..100
        "reason": reason,                # explicação objetiva do match
        "subject": {
            "full_name": r.full_name,
            "aka": r.aka,
            "bi": r.bi,
            "passport": r.passport,
            "dob": (r.dob.isoformat() if r.dob else None),
            "nationality": r.nationality,
        },
        "pep": {
            "category": r.pep_category,
            "role": r.pep_role,
            "country": r.country,
            "start_date": (r.start_date.isoformat() if r.start_date else None),
            "end_date": (r.end_date.isoformat() if r.end_date else None),
            "risk_level": r.risk_level,
        },
        "reference": {
            "source_ref": r.source_ref,
            "note": r.note,
            "record_id": r.id,
        },
    }
