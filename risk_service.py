from datetime import datetime, date
from typing import List, Tuple, Dict

from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app import models
from config import settings
from utils import normalize_text, normalize_id, simple_similarity, classify_level


def _adjust_by_country(country_code: str | None) -> int:
    if not country_code:
        return 0
    # regra simples: poderás mais tarde puxar isto de tabela
    high_risk_countries = {"AO"}  # exemplo
    low_risk_countries = {"PT", "DE", "FR"}
    cc = country_code.upper()
    if cc in high_risk_countries:
        return 10
    if cc in low_risk_countries:
        return -5
    return 0


def find_candidates(
    db: Session,
    full_name: str,
    nif: str | None,
    passport: str | None,
    resident_card: str | None,
) -> List[models.NormalizedEntity]:
    q_name_norm = normalize_text(full_name) or ""
    q_nif = normalize_id(nif)
    q_pass = normalize_id(passport)
    q_card = normalize_id(resident_card)

    query = db.query(models.NormalizedEntity)
    conditions = []

    if q_nif:
        conditions.append(models.NormalizedEntity.nif_norm == q_nif)
    if q_pass:
        conditions.append(models.NormalizedEntity.passport_norm == q_pass)
    if q_card:
        conditions.append(models.NormalizedEntity.resident_card_norm == q_card)

    if conditions:
        query = query.filter(or_(*conditions))
    else:
        # fallback: nomes semelhantes
        query = query.filter(
            func.length(models.NormalizedEntity.full_name_norm) > 0  # só para ter algo
        )

    # limitar a, por exemplo, 100 candidatos
    candidates = query.limit(100).all()

    # se não vierem por ID, aplicar filtro de similaridade mínima
    if not conditions:
        filtered = []
        for e in candidates:
            sim = simple_similarity(q_name_norm, e.full_name_norm or "")
            if sim >= 0.5:
                filtered.append(e)
        return filtered
    return candidates


def calculate_match_score(
    input_data: dict, entity: models.NormalizedEntity
) -> Tuple[int, List[str]]:
    factors: List[str] = []
    base = entity.source_risk_weight or settings.RISK_WEIGHTS.get(
        entity.source_type, 40
    )

    factors.append(f"Fonte {entity.source_type} (peso base {base})")

    # Similaridade de nome
    sim = simple_similarity(input_data["full_name"], entity.full_name_norm or "")
    if sim > 0:
        bonus = int(sim * 10)
        base += bonus
        factors.append(f"Similaridade de nome {int(sim * 100)}% (+{bonus})")

    # Match de documento
    id_match = False
    if input_data.get("nif") and entity.nif_norm:
        if normalize_id(input_data["nif"]) == entity.nif_norm:
            id_match = True
    if input_data.get("passport") and entity.passport_norm:
        if normalize_id(input_data["passport"]) == entity.passport_norm:
            id_match = True
    if input_data.get("resident_card") and entity.resident_card_norm:
        if normalize_id(input_data["resident_card"]) == entity.resident_card_norm:
            id_match = True

    if id_match:
        base += 10
        factors.append("Documento (NIF/passaporte/cartão) coincidente (+10)")

    # País
    country_adj = _adjust_by_country(input_data.get("country"))
    if country_adj:
        base += country_adj
        if country_adj > 0:
            factors.append(f"País de alto risco (+{country_adj})")
        else:
            factors.append(f"País de baixo risco ({country_adj})")

    final_score = max(0, min(100, base))
    return final_score, factors


def aggregate_matches(
    matches: List[Tuple[models.NormalizedEntity, int, List[str]]]
) -> List[Dict]:
    grouped: Dict[str, Dict] = {}
    for entity, score, factors in matches:
        key = entity.nif_norm or entity.full_name_norm
        if not key:
            key = f"ENT_{entity.id}"
        if key not in grouped:
            grouped[key] = {
                "entity": entity,
                "sources": set(),
                "scores": [],
                "factors": [],
            }
        grouped[key]["sources"].add(entity.source_type)
        grouped[key]["scores"].append(score)
        grouped[key]["factors"].extend(factors)

    result: List[Dict] = []
    for g in grouped.values():
        base_score = max(g["scores"])
        bonus = len(g["sources"]) * 3
        final_score = min(100, base_score + bonus)
        entity: models.NormalizedEntity = g["entity"]
        result.append(
            {
                "entity": entity,
                "sources": list(g["sources"]),
                "score": final_score,
                "factors": g["factors"],
            }
        )

    result.sort(key=lambda x: x["score"], reverse=True)
    return result


def create_risk_record(
    db: Session, user: models.User, payload: dict
) -> models.RiskRecord:
    full_name_norm = normalize_text(payload["full_name"]) or payload["full_name"]
    rec = models.RiskRecord(
        full_name=payload["full_name"],
        full_name_norm=full_name_norm,
        nif=normalize_id(payload.get("nif")),
        passport=normalize_id(payload.get("passport")),
        resident_card=normalize_id(payload.get("resident_card")),
        country_code=(payload.get("country") or None),
        score=0,
        level="LOW",
        decision="PENDING",
        analyst_id=user.id,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def update_risk_with_result(
    db: Session,
    risk_record: models.RiskRecord,
    score: int,
    explanation: List[str],
):
    risk_record.score = score
    risk_record.level = classify_level(score)
    risk_record.explanation = {"fatores": explanation}
    db.add(risk_record)
    db.commit()
    db.refresh(risk_record)


def get_dashboard_stats(db: Session) -> Dict:
    today = date.today()
    start = datetime(today.year, today.month, today.day)
    end = datetime(today.year, today.month, today.day, 23, 59, 59)

    total_today = (
        db.query(models.RiskRecord)
        .filter(models.RiskRecord.created_at >= start)
        .filter(models.RiskRecord.created_at <= end)
        .count()
    )

    high_critical = (
        db.query(models.RiskRecord)
        .filter(models.RiskRecord.level.in_(["HIGH", "CRITICAL"]))
        .count()
    )

    avg_time = 0.0  # se houver campo de tempo de análise, calcula aqui

    last_records = (
        db.query(models.RiskRecord)
        .order_by(models.RiskRecord.created_at.desc())
        .limit(10)
        .all()
    )

    results = []
    for r in last_records:
        results.append(
            {
                "analysis_id": r.id,
                "data": r.created_at,
                "nome": r.full_name,
                "score": r.score,
                "nivel": r.level,
                "decisao": r.decision,
            }
        )

    return {
        "total_analises_hoje": total_today,
        "casos_high_critical": high_critical,
        "tempo_medio_analise_segundos": avg_time,
        "ultimas_analises": results,
    }

class RiskRecord(Base):
    __tablename__ = "risk_records"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    full_name = Column(String(255), nullable=False)
    nif = Column(String(100), nullable=True)
    passport = Column(String(100), nullable=True)
    resident_card = Column(String(100), nullable=True)
    country = Column(String(3), nullable=True)

    score = Column(Integer, nullable=False)
    level = Column(String(20), nullable=False)          # <- usa RiskLevel.value
    decision = Column(String(50), nullable=True)        # <- usa RiskDecision.value
    decision_notes = Column(Text, nullable=True)
    explanation = Column(JSON, nullable=True)

    confirmed_entity_id = Column(Integer, ForeignKey("normalized_entities.id"), nullable=True)
    analyst_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    analyst = relationship("User", back_populates="risk_records")
    confirmed_entity = relationship("NormalizedEntity")
    alerts = relationship("RiskAlert", back_populates="risk_record")
