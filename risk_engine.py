"""
risk_engine.py
Motor de Risco – Versão simplificada e compatível com o main.py
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from models import NormalizedEntity, RiskRecord, RiskLevel


# ============================================================
# 1. NORMALIZAÇÃO / HELPERS
# ============================================================

def _norm(value: Optional[str]) -> Optional[str]:
    """Normaliza texto para comparação (upper + trim)."""
    if not value:
        return None
    return value.strip().upper()


def normalize_text(value: Optional[str]) -> Optional[str]:
    """Função usada em vários sítios para normalizar texto."""
    return _norm(value)


def _get_attr(obj: Any, key: str) -> Optional[str]:
    """
    Lê um atributo de um dict ou de um objecto ORM de forma segura.
    """
    if obj is None:
        return None

    if isinstance(obj, dict):
        return obj.get(key)

    if hasattr(obj, key):
        return getattr(obj, key)

    return None


# ============================================================
# 2. FIND CANDIDATES – Multi-match
# ============================================================

def find_candidates(
    db: Session,
    name: Optional[str] = None,
    nif: Optional[str] = None,
    passport: Optional[str] = None,
    resident_card: Optional[str] = None,
    nationality: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Pesquisa candidatos na tabela NormalizedEntity.

    Devolve sempre uma lista de dicts com campos básicos
    que o frontend espera (id, name, nif, etc.).
    """

    query = db.query(NormalizedEntity)
    filters = []

    if name:
        filters.append(NormalizedEntity.normalized_name.ilike(f"%{_norm(name)}%"))

    if nif:
        filters.append(NormalizedEntity.nif == _norm(nif))

    if passport:
        filters.append(NormalizedEntity.passport == _norm(passport))

    if resident_card:
        filters.append(NormalizedEntity.resident_card == _norm(resident_card))

    if nationality:
        filters.append(NormalizedEntity.country == _norm(nationality))

    if filters:
        query = query.filter(or_(*filters))

    results = query.limit(limit).all()

    candidates: List[Dict[str, Any]] = []
    for e in results:
        candidates.append(
            {
                "id": e.id,
                "name": e.name,
                "normalized_name": e.normalized_name,
                "nif": e.nif,
                "passport": e.passport,
                "resident_card": e.resident_card,
                "country": e.country,
                "info_source_id": e.info_source_id,
            }
        )

    return candidates


# ============================================================
# 3. MATCH SCORE – Similaridade simples (0–100)
# ============================================================

def calculate_match_score(
    candidate: Any,
    search: Dict[str, Any],
) -> float:
    """
    Calcula um score de semelhança (0–100) entre o candidato e
    os parâmetros de pesquisa.
    """

    score = 0.0

    # NIF
    nif_s = _norm(search.get("nif"))
    nif_c = _norm(_get_attr(candidate, "nif"))
    if nif_s and nif_c and nif_s == nif_c:
        score += 60.0

    # Passaporte
    pass_s = _norm(search.get("passport"))
    pass_c = _norm(_get_attr(candidate, "passport"))
    if pass_s and pass_c and pass_s == pass_c:
        score += 40.0

    # Cartão de residente
    rc_s = _norm(search.get("resident_card"))
    rc_c = _norm(_get_attr(candidate, "resident_card"))
    if rc_s and rc_c and rc_s == rc_c:
        score += 40.0

    # Nome aproximado (substring simples)
    name_s = _norm(search.get("name"))
    name_c = _norm(
        _get_attr(candidate, "normalized_name") or _get_attr(candidate, "name")
    )
    if name_s and name_c and name_s in name_c:
        score += 20.0

    # Nacionalidade
    nat_s = _norm(search.get("nationality") or search.get("country"))
    nat_c = _norm(_get_attr(candidate, "country"))
    if nat_s and nat_c and nat_s == nat_c:
        score += 10.0

    # Clamp
    if score < 0:
        score = 0.0
    if score > 100:
        score = 100.0

    return float(score)


# ============================================================
# 4. AGGREGATE MATCHES – Ordenar e devolver top N
# ============================================================

def aggregate_matches(
    candidates: List[Any],
    search: Dict[str, Any],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    """
    Recebe uma lista de candidatos (dict ou ORM) e devolve uma lista de
    dicts ordenados por match_score descrescente.
    """

    aggregated: List[Dict[str, Any]] = []

    if not isinstance(candidates, list):
        candidates = list(candidates)

    for cand in candidates:
        score = calculate_match_score(candidate=cand, search=search)

        if isinstance(cand, dict):
            item = dict(cand)
        else:
            item = {
                "id": getattr(cand, "id", None),
                "name": getattr(cand, "name", None),
                "normalized_name": getattr(cand, "normalized_name", None),
                "nif": getattr(cand, "nif", None),
                "passport": getattr(cand, "passport", None),
                "resident_card": getattr(cand, "resident_card", None),
                "country": getattr(cand, "country", None),
                "info_source_id": getattr(cand, "info_source_id", None),
            }

        item["match_score"] = score
        aggregated.append(item)

    aggregated.sort(key=lambda x: x.get("match_score", 0.0), reverse=True)
    return aggregated[:top_n]


# ============================================================
# 5. ANALYSE RISK REQUEST – função genérica
# ============================================================

def analyze_risk_request(
    db: Session,
    name: str,
    nif: Optional[str] = None,
    passport: Optional[str] = None,
    resident_card: Optional[str] = None,
    nationality: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Devolve score, level, factors e candidates.
    """
    search = {
        "name": name,
        "nif": nif,
        "passport": passport,
        "resident_card": resident_card,
        "nationality": nationality,
    }

    candidates = find_candidates(
        db,
        name=name,
        nif=nif,
        passport=passport,
        resident_card=resident_card,
        nationality=nationality,
    )

    aggregated = aggregate_matches(candidates, search=search)

    best_score = max([c["match_score"] for c in aggregated], default=0.0)

    # score → level
    if best_score >= 80:
        level = RiskLevel.HIGH
    elif best_score >= 40:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    factors: List[str] = []
    if aggregated:
        factors.append("Foram encontrados registos relevantes nas bases internas.")
    if best_score >= 80:
        factors.append("Alta probabilidade de correspondência com perfis de risco.")
    elif best_score >= 40:
        factors.append("Existe semelhança moderada com registos existentes.")
    else:
        factors.append("Baixa semelhança com registos de risco conhecidos.")

    return {
        "score": best_score,
        "level": level.value,
        "factors": factors,
        "candidates": aggregated,
    }


# ============================================================
# 6. CONFIRM MATCH AND PERSIST – confirmar entidade escolhida
# ============================================================

def confirm_match_and_persist(
    db: Session,
    risk_record: RiskRecord,
    chosen_candidate_id: Optional[int] = None,
) -> RiskRecord:
    """
    Confirma o match escolhido pelo analista e actualiza o RiskRecord.
    Usa o campo 'confirmed_entity_id' definido em models.RiskRecord.
    """
    if chosen_candidate_id is not None:
        setattr(risk_record, "confirmed_entity_id", chosen_candidate_id)

    db.add(risk_record)
    db.commit()
    db.refresh(risk_record)
    return risk_record


# ============================================================
# 7. GET HISTORY FOR IDENTIFIER – histórico por NIF/passaporte/etc.
# ============================================================

def get_history_for_identifier(
    db: Session,
    identifier: str,
) -> List[RiskRecord]:
    """
    Devolve o histórico de análises para um identificador único:
    NIF, passaporte ou cartão de residente.
    """
    ident = (identifier or "").strip().upper()
    if not ident:
        return []

    records = (
        db.query(RiskRecord)
        .filter(
            or_(
                RiskRecord.nif == ident,
                RiskRecord.passport == ident,
                RiskRecord.resident_card == ident,
            )
        )
        .order_by(RiskRecord.created_at.desc())
        .all()
    )

    return records
