# risk_engine.py
"""
Módulo de motor de risco para o Check Insurance Risk.

Objectivos:
- Centralizar a lógica de:
  - procura de candidatos em NormalizedEntity
  - análise de risco
  - confirmação de match
  - histórico de um assegurado

O mais importante neste momento é garantir que:
- as funções existem com estes nomes:
    - find_candidates
    - analyze_risk_request
    - confirm_match_and_persist
    - get_history_for_identifier
- assim o main.py deixa de dar ImportError ao arrancar.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from models import NormalizedEntity, RiskRecord, RiskLevel


# -------------------------------------------------------------------------
# Função utilitária simples para normalizar identificadores
# -------------------------------------------------------------------------
def _norm(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.strip().upper()


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

    Esta função é chamada pelo main.py. É CRÍTICO que o nome exista.
    A implementação é simples de propósito; depois podemos afiná-la.
    """
    query = db.query(NormalizedEntity)

    filters = []

    if name:
        # assumindo que tens um campo normalized_name ou similar
        # se o nome for diferente na tua tabela, ajusta aqui.
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
# 2. ANALYSE RISK REQUEST  (chamado quando o analista faz uma nova análise)
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
    Neste momento, devolve sempre um LOW score (10) só para o sistema arrancar.

    MAIS TARDE:
    - usar find_candidates()
    - aplicar regras de PEP, sanções, fraude, sinistros, etc.
    """
    candidates = find_candidates(
        db=db,
        name=name,
        nif=nif,
        passport=passport,
        resident_card=resident_card,
        nationality=nationality,
        limit=50,
    )

    # Placeholder de lógica de score
    score = 10
    level = RiskLevel.LOW
    factors: List[str] = []

    if candidates:
        factors.append("Encontrados candidatos em bases internas de risco.")

    return {
        "score": score,
        "level": level,
        "factors": factors,
        "candidates": candidates,
    }


# -------------------------------------------------------------------------
# 3. CONFIRM MATCH AND PERSIST  (quando o analista escolhe o match certo)
# -------------------------------------------------------------------------
def confirm_match_and_persist(
    db: Session,
    risk_record: RiskRecord,
    chosen_candidate_id: Optional[int] = None,
) -> RiskRecord:
    """
    Confirma o match escolhido pelo analista e actualiza o RiskRecord.

    Por enquanto, apenas grava o ID do candidato e devolve o mesmo registo.
    Se a tua tabela RiskRecord não tiver estes campos, podes ajustar.
    """
    if chosen_candidate_id is not None:
        # assumindo que tens um campo "matched_entity_id" na tabela RiskRecord
        setattr(risk_record, "matched_entity_id", chosen_candidate_id)

    db.add(risk_record)
    db.commit()
    db.refresh(risk_record)
    return risk_record


# -------------------------------------------------------------------------
# 4. GET HISTORY FOR IDENTIFIER  (histórico de um assegurado)
# -------------------------------------------------------------------------
def get_history_for_identifier(
    db: Session,
    identifier: str,
) -> List[RiskRecord]:
    """
    Devolve o histórico de análises para um NIF / passaporte / cartão.
    Implementação simplificada: assume que a coluna "search_identifier"
    existe em RiskRecord. Se for outro nome, ajusta no filtro.
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
