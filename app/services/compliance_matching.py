import re
from sqlalchemy.orm import Session
from app.models_compliance import ComplianceRecord, ComplianceHit
from datetime import datetime

def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _simple_name_score(a: str, b: str) -> int:
    # score simples para MVP: tokens comuns
    A = set(_norm(a).split())
    B = set(_norm(b).split())
    if not A or not B:
        return 0
    inter = len(A & B)
    union = len(A | B)
    return int((inter / union) * 100)

def match_category(
    db: Session,
    entity_id: str,
    risk_id: str,
    category: str,
    full_name: str,
    id_number: str | None = None,
    nationality: str | None = None,
    min_score: int = 75,
):
    q = db.query(ComplianceRecord).filter(
        ComplianceRecord.entity_id == entity_id,
        ComplianceRecord.category == category,
    )

    # pré-filtro leve: ILIKE no nome (ajuda performance)
    like = f"%{full_name.split()[0]}%" if full_name else "%"
    q = q.filter(ComplianceRecord.full_name.ilike(like))

    hits = []
    for rec in q.limit(500).all():
        score = _simple_name_score(full_name, rec.full_name)
        reason = {"name_score": score}

        # bônus por doc
        if id_number and rec.id_number and id_number == rec.id_number:
            score = max(score, 95)
            reason["id_match"] = True

        # bônus leve por nacionalidade
        if nationality and rec.nationality and _norm(nationality) == _norm(rec.nationality):
            score = min(100, score + 5)
            reason["nationality_bonus"] = True

        if score >= min_score:
            hit = ComplianceHit(
                entity_id=entity_id,
                risk_id=risk_id,
                category=category,
                source_system=rec.source_system,
                record_id=rec.id,
                match_score=score,
                match_reason=reason,
                snapshot={
                    "full_name": rec.full_name,
                    "nationality": rec.nationality,
                    "dob": rec.dob,
                    "id_number": rec.id_number,
                    "aliases": rec.aliases,
                    "risk_level": rec.risk_level,
                    "source_system": rec.source_system,
                    "source_ref": rec.source_ref,
                    "raw": rec.raw,
                },
                matched_at=datetime.utcnow(),
            )
            hits.append(hit)

    if hits:
        db.add_all(hits)
        db.commit()

    # devolve já agrupado por fonte (para PDF)
    out = {}
    for h in hits:
        out.setdefault(h.source_system, []).append(
            {"match_score": h.match_score, **(h.snapshot or {})}
        )
    return out
