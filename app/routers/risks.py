from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_perm
from app.models import Risk, Source
from app.models_source_records import SourceRecord

router = APIRouter()


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _compute_risk(matches: dict):
    if matches["sanctions"]:
        return 95, "Match em listas de sanções. Risco crítico."
    if matches["pep"]:
        return 70, "PEP identificado."
    if matches["adverse_media"]:
        return 55, "Adverse media identificada."
    if matches["watchlists"]:
        return 50, "Presença em watchlist."
    return 20, "Sem matches relevantes."


@router.post("/risks/{risk_id}/confirm")
def confirm_risk(
    risk_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_perm("risks:update")),
):
    risk = db.query(Risk).filter(Risk.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk não encontrado")

    subject = _norm(risk.full_name)

    records = (
        db.query(SourceRecord, Source)
        .join(Source, Source.id == SourceRecord.source_id)
        .filter(SourceRecord.entity_id == risk.entity_id)
        .all()
    )

    matches = {
        "pep": [],
        "sanctions": [],
        "watchlists": [],
        "adverse_media": [],
    }

    for rec, src in records:
        if _norm(rec.subject_name) != subject:
            continue

        hit = rec.raw.copy()
        hit["source_name"] = src.name

        if rec.category == "PEP":
            matches["pep"].append(hit)
        elif rec.category == "SANCTIONS":
            matches["sanctions"].append(hit)
        elif rec.category == "WATCHLIST":
            matches["watchlists"].append(hit)
        else:
            matches["adverse_media"].append(hit)

    score, summary = _compute_risk(matches)

    risk.score = score
    risk.justification = summary
    risk.matches = matches

    db.commit()

    return {
        "score": score,
        "summary": summary,
        "matches": matches,
    }
