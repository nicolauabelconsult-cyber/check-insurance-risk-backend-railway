# risk_engine.py
"""
Módulo de motor de risco para o Check Insurance Risk.

Objectivos:
- Centralizar a lógica de:
  - procura de candidatos em NormalizedEntity
  - cálculo de score de match
  - análise de risco
  - confirmação de match
  - histórico de um assegurado

O mais importante neste momento é garantir que existem estas funções:
    - find_candidates
    - calculate_match_score
    - analyze_risk_request
    - confirm_match_and_persist
    - get_history_for_identifier
para satisfazer os imports do main.py.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from models import NormalizedEntity, RiskRecord, RiskLevel


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def _norm(value: Optional[str]) -> Optional[str]:
    """Normaliza strings (trim + upper)."""
    if not value:
        return None
    return value.strip().upper()


def _get_attr(obj: Any, key: str) -> Optional[str]:
    """
    Tenta obter um valor seja de dict seja de objecto.
    Usa getattr e .get de forma segura.
    """
    if obj is None:
        return None

    # dict-like
    if isinstance(obj, dict):
        return obj.get(key)

    # object-like
    if hasattr(obj, key):
        return getattr(obj, key)

    return None


# -------------------------------------------------------------------------
# 1. FIND CANDIDATES  (usado para multi-match)
# -------------------------------------------------------------------------
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
    Procura candidatos na tabela NormalizedEntity.

    Esta função é chamada pelo main.py. O nome PRECISA de existir.
    Implementação simples; depois afinamos regras.
    """
    query = db.query(NormalizedEntity)

    filters = []

    if name:
        # ajusta aqui se o campo se chamar diferente na BD
        filters.append(
            NormalizedEntity.normalized_name.ilike(f"%{name.strip().upper()}%")
        )

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
                "name": getattr(e, "name", None),
                "normalized_name": getattr(e, "normalized_name", None),
                "nif": getattr(e, "nif", None),
                "passport": getattr(e, "passport", None),
                "resident_card": getattr(e, "resident_card", None),
                "country": getattr(e, "country", None),
                "info_source_id": getattr(e, "info_source_id", None),
            }
        )

    return candidates


# -------------------------------------------------------------------------
# 2. CALCULATE MATCH SCORE  (NOVO – exigido pelo main.py)
# -------------------------------------------------------------------------
def calculate_match_score(*args, **kwargs) -> float:
    """
    Calcula um score de similaridade entre o candidato e os parâmetros de pesquisa.

    Usamos *args/**kwargs para ser tolerante à forma como o main.py chama
    esta função. Tentamos inferir:

        candidate  -> primeiro argumento posicional ou kwargs["candidate"]
        search     -> segundo argumento posicional ou kwargs["search"/"params"]

    Devolve sempre um float entre 0 e 100.
    """

    # --- tentar extrair argumentos de forma flexível ----------------------
    candidate: Any = None
    search: Dict[str, Any] = {}

    if "candidate" in kwargs:
        candidate = kwargs["candidate"]
    elif args:
        candidate = args[0]

    if "search" in kwargs:
        search = kwargs["search"] or {}
    elif "params" in kwargs:
        search = kwargs["params"] or {}
    elif len(args) > 1:
        search = args[1] or {}
    else:
        search = {}

    # garantir que é dict
    if not isinstance(search, dict):
        search = {}

    # --- regras simples de score -----------------------------------------
    score = 0.0

    # NIF exacto pesa bastante
    nif_search = _norm(search.get("nif"))
    nif_cand = _norm(_get_attr(candidate, "nif"))
    if nif_search and nif_cand and nif_search == nif_cand:
        score += 60.0

    # Passaporte exacto
    pass_search = _norm(search.get("passport"))
    pass_cand = _norm(_get_attr(candidate, "passport"))
    if pass_search and pass_cand and pass_search == pass_cand:
        score += 40.0

    # Cartão de residente exacto
    rc_search = _norm(search.get("resident_card"))
    rc_cand = _norm(_get_attr(candidate, "resident_card"))
    if rc_search and rc_cand and rc_search == rc_cand:
        score += 40.0

    # Nome semelhante (substring simples)
    name_search = _norm(search.get("name"))
    name_cand = _norm(_get_attr(candidate, "normalized_name") or _get_attr(candidate, "name"))
    if name_search and name_cand and name_search in name_cand:
        score += 20.0

    # Nacionalidade igual
    nat_search = _norm(search.get("nationality") or search.get("country"))
    nat_cand = _norm(_get_attr(candidate, "country"))
    if nat_search and nat_cand and nat_search == nat_cand:
        score += 10.0

    # clamp para [0, 100]
    if score < 0:
        score = 0.0
    if score > 100:
        score = 100.0

    return float(score)


# -------------------------------------------------------------------------
# 3. ANALYSE RISK REQUEST  (nova análise de risco)
# -------------------------------------------------------------------------
def analyze_risk_request(
    db: Session,
    name: str,
    nif: Optional[str] = None,
    passport: Optional[str] = None,
    resident_card: Optional[str] = None,
    nationality: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Faz uma análise simplificada de risco.

    Neste momento:
    - obtém candidatos com find_candidates
    - calcula um score máximo com calculate_match_score
    - converte esse score num nível de risco simples
    """

    search_params = {
        "name": name,
        "nif": nif,
        "passport": passport,
        "resident_card": resident_card,
        "nationality": nationality,
    }

    candidates = find_candidates(
        db=db,
        name=name,
        nif=nif,
        passport=passport,
        resident_card=resident_card,
        nationality=nationality,
        limit=50,
    )

    # calcular melhor score entre candidatos
    best_score = 0.0
    for c in candidates:
        s = calculate_match_score(candidate=c, search=search_params)
        if s > best_score:
            best_score = s

    # mapear score -> nível de risco
    if best_score >= 80:
        level = RiskLevel.HIGH
    elif best_score >= 40:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    factors: List[str] = []
    if candidates:
        factors.append("Foram encontrados registos nas bases internas.")
    if best_score >= 80:
        factors.append("Existe forte semelhança com registos de risco conhecidos.")
    elif best_score >= 40:
        factors.append("Existe alguma semelhança com registos existentes.")

    return {
        "score": best_score,
        "level": level,
        "factors": factors,
        "candidates": candidates,
    }


# -------------------------------------------------------------------------
# 4. CONFIRM MATCH AND PERSIST  (quando o analista escolhe o match)
# -------------------------------------------------------------------------
def confirm_match_and_persist(
    db: Session,
    risk_record: RiskRecord,
    chosen_candidate_id: Optional[int] = None,
) -> RiskRecord:
    """
    Confirma o match escolhido pelo analista e actualiza o RiskRecord.

    Se a tua tabela RiskRecord não tiver 'matched_entity_id',
    podes trocar pelo campo correcto.
    """
    if chosen_candidate_id is not None:
        setattr(risk_record, "matched_entity_id", chosen_candidate_id)

    db.add(risk_record)
    db.commit()
    db.refresh(risk_record)
    return risk_record


# -------------------------------------------------------------------------
# 5. GET HISTORY FOR IDENTIFIER  (histórico do cliente)
# -------------------------------------------------------------------------
def get_history_for_identifier(
    db: Session,
    identifier: str,
) -> List[RiskRecord]:
    """
    Devolve o histórico de análises para um NIF / passaporte / cartão.

    Ajusta os campos no filtro se na tua tabela RiskRecord os nomes
    forem diferentes.
    """
    identifier = identifier.strip()

    q = (
        db.query(RiskRecord)
        .filter(
            (RiskRecord.nif == identifier)
            | (RiskRecord.passport == identifier)
            | (RiskRecord.resident_card == identifier)
        )
        .order_by(RiskRecord.created_at.desc())
    )

    return q.all()
