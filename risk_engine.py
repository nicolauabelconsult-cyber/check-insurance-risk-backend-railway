"""
Motor de Risco – Versão Final
100% compatível com backend + frontend + reporting
"""

from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Any, Dict, List, Optional, Tuple

from models import NormalizedEntity, RiskRecord, RiskLevel

# ============================================================
# 1. NORMALIZAÇÃO
# ============================================================

def _norm(value: Optional[str]) -> Optional[str]:
    """Normaliza texto para comparação."""
    if not value:
        return None
    return value.strip().upper()


def normalize_text(value: Optional[str]) -> Optional[str]:
    """Compatível com versões antigas."""
    return _norm(value)


def _get_attr(obj: Any, key: str) -> Optional[str]:
    """Lê valores de um dict ou de um ORM."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


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

    candidates = []
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
# 3. MATCH SCORE – Similaridade
# ============================================================

def calculate_match_score(
    candidate: Any,
    search: Dict[str, Any],
) -> float:
    """
    Calcula o score de semelhança (0–100).
    """

    score = 0.0

    # NIF
    nif_s = _norm(search.get("nif"))
    nif_c = _norm(_get_attr(candidate, "nif"))
    if nif_s and nif_c and nif_s == nif_c:
        score += 60

    # Passaporte
    pass_s = _norm(search.get("passport"))
    pass_c = _norm(_get_attr(candidate, "passport"))
    if pass_s and pass_c and pass_s == pass_c:
        score += 40

    # Cartão de residente
    rc_s = _norm(search.get("resident_card"))
    rc_c = _norm(_get_attr(candidate, "resident_card"))
    if rc_s and rc_c and rc_s == rc_c:
        score += 40

    # Nome aproximado (substring simples)
    name_s = _norm(search.get("name"))
    name_c = _norm(
        _get_attr(candidate, "normalized_name") or _get_attr(candidate, "name")
    )
    if name_s and name_c and name_s in name_c:
        score += 20

    # Nacionalidade
    nat_s = _norm(search.get("nationality") or search.get("country"))
    nat_c = _norm(_get_attr(candidate, "country"))
    if nat_s and nat_c and nat_s == nat_c:
        score += 10

    # Limitar
    return min(100, max(0, float(score)))


# ============================================================
# 4. AGGREGATE MATCHES – Top candidatos organizados
# ============================================================

def aggregate_matches(
    candidates: List[Any],
    search: Dict[str, Any],
    top_n: int = 10,
) -> List[Dict[str, Any]]:
    result = []

    for cand in candidates:
        score = calculate_match_score(candidate=cand, search=search)

        entry = dict(cand) if isinstance(cand, dict) else {
            "id": getattr(cand, "id", None),
            "name": getattr(cand, "name", None),
            "normalized_name": getattr(cand, "normalized_name", None),
            "nif": getattr(cand, "nif", None),
            "passport": getattr(cand, "passport", None),
            "resident_card": getattr(cand, "resident_card", None),
            "country": getattr(cand, "country", None),
            "info_source_id": getattr(cand, "info_source_id", None),
        }

        entry["match_score"] = score
        result.append(entry)

    result.sort(key=lambda x: x["match_score"], reverse=True)
    return result[:top_n]


# ============================================================
# 5. ANALYSE RISK REQUEST – Processo completo
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
    Processo principal da análise.
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

    best_score = max([c["match_score"] for c in aggregated], default=0)

    # Convert score → level
    if best_score >= 80:
        level = RiskLevel.HIGH
    elif best_score >= 40:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    factors = []
    if aggregated:
        factors.append("Foram encontrados registos relevantes nas bases internas.")
    if best_score >= 80:
        factors.append("Alta probabilidade de correspondência")

def confirm_match_and_persist(
    db: Session,
    risk_record: RiskRecord,
    chosen_candidate_id: Optional[int] = None,
) -> RiskRecord:
    """
    Confirma o match escolhido pelo analista e actualiza o RiskRecord.

    - risk_record: registo de risco já existente na BD
    - chosen_candidate_id: ID da entidade (NormalizedEntity) escolhida como match

    Se a tua tabela RiskRecord tiver outro nome de campo,
    troca 'confirmed_entity_id' pelo campo correcto.
    """
    if chosen_candidate_id is not None:
        # campo definido em models.RiskRecord
        setattr(risk_record, "confirmed_entity_id", chosen_candidate_id)

    db.add(risk_record)
    db.commit()
    db.refresh(risk_record)
    return risk_record
