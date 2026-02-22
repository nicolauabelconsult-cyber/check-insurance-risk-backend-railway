import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..db import get_db
from ..deps import require_perm, get_current_user
from ..models import Risk, RiskStatus
from ..models import Source
from ..models_source_records import SourceRecord
from ..schemas import (
    RiskOut,
    RiskSearchIn,
    RiskSearchOut,
    RiskConfirmIn,
    CandidateOut,
)

from ..pdfs import (
    build_risk_pdf_institutional_pt,
    make_integrity_hash,
    make_server_signature,
)
from ..settings import settings

router = APIRouter(prefix="/risks", tags=["risks"])


def _ensure_scope(user, entity_id: str) -> None:
    role_val = getattr(getattr(user, "role", None), "value", getattr(user, "role", None))
    if role_val == "SUPER_ADMIN":
        return
    if not getattr(user, "entity_id", None):
        raise HTTPException(status_code=403, detail="Entity scope missing")
    if user.entity_id != entity_id:
        raise HTTPException(status_code=403, detail="Sem permissão para esta entidade")


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _score(query: str, subject: str) -> int:
    if not query or not subject:
        return 0
    if query == subject:
        return 95
    if subject.startswith(query) or query.startswith(subject):
        return 85
    if query in subject or subject in query:
        return 75
    return 60


@router.post("/search", response_model=RiskSearchOut)
def search_risk(
    payload: RiskSearchIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Pesquisa em source_records (import oficial) e devolve candidatos.

    ✅ Importante: RiskSearchOut tem apenas:
      - disambiguation_required
      - candidates
    """
    entity_id = payload.entity_id or getattr(user, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    _ensure_scope(user, entity_id)

    full_name = (payload.full_name or "").strip()
    if not full_name:
        raise HTTPException(status_code=400, detail="name is required")

    qname = _norm(full_name)

    # Cria o Risk (DRAFT) para auditoria/rastreio
    risk = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        created_by=user.id,
        query_name=full_name,
        query_nationality=payload.nationality,
        status=RiskStatus.DRAFT,
        matches=[],
    )
    db.add(risk)
    db.commit()

    # 🔎 Procura simples (contains) em SourceRecord.subject_name
    # Nota: subject_name já está guardado em lowercase no upload.
    recs = (
        db.query(SourceRecord, Source)
        .join(Source, Source.id == SourceRecord.source_id)
        .filter(SourceRecord.entity_id == entity_id)
        .filter(SourceRecord.subject_name.ilike(f"%{qname}%"))
        .order_by(SourceRecord.created_at.desc())
        .limit(50)
        .all()
    )

    # Agrega por subject_name
    by_subject: dict[str, dict] = {}
    for rec, src in recs:
        subj = rec.subject_name or ""
        if subj not in by_subject:
            by_subject[subj] = {
                "id": str(rec.id),
                "full_name": (rec.raw.get("full_name") or rec.raw.get("subject_name") or rec.raw.get("entity_name") or subj),
                "nationality": rec.raw.get("country") or rec.country,
                "dob": rec.raw.get("date_of_birth"),
                "doc_type": None,
                "doc_last4": None,
                "sources": set(),
                "match_score": _score(qname, subj),
                "raw_samples": [],
            }
        by_subject[subj]["sources"].add(src.name)
        if len(by_subject[subj]["raw_samples"]) < 5:
            by_subject[subj]["raw_samples"].append(
                {
                    "category": rec.category,
                    "source": src.name,
                    "raw": rec.raw,
                }
            )

    candidates = []
    for subj, v in by_subject.items():
        candidates.append(
            CandidateOut(
                id=v["id"],
                full_name=v["full_name"],
                nationality=v["nationality"],
                dob=v["dob"],
                doc_type=v["doc_type"],
                doc_last4=v["doc_last4"],
                sources=sorted(list(v["sources"])),
                match_score=int(v["match_score"]),
            )
        )

    # guarda matches (para PDF/auditoria futura), mesmo antes do confirm
    risk.matches = [
        {
            "candidate_id": c.id,
            "full_name": c.full_name,
            "nationality": c.nationality,
            "match_score": c.match_score,
            "sources": c.sources,
        }
        for c in candidates
    ]
    # score simples: max candidate score
    risk.score = str(max([c.match_score for c in candidates], default=0))
    risk.summary = "Correspondências encontradas." if candidates else "Sem correspondência nas fontes disponíveis."
    db.commit()

    disambiguation = len(candidates) > 1
    return RiskSearchOut(disambiguation_required=disambiguation, candidates=candidates)


@router.post("/confirm", response_model=RiskOut)
def confirm_no_match(
    payload: RiskConfirmIn,
    db: Session = Depends(get_db),
    user=Depends(require_perm("risk:confirm")),
):
    entity_id = payload.entity_id or getattr(user, "entity_id", None)
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    _ensure_scope(user, entity_id)

    if not (payload.name or "").strip():
        raise HTTPException(status_code=400, detail="name is required")
    if not (payload.nationality or "").strip():
        raise HTTPException(status_code=400, detail="nationality is required")
    if not (payload.id_number or "").strip():
        raise HTTPException(status_code=400, detail="id_number is required")

    is_no_match = payload.candidate_id == "NO_MATCH"

    risk = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        created_by=user.id,
        query_name=payload.name.strip(),
        query_nationality=payload.nationality.strip(),
        query_bi=payload.id_number.strip() if payload.id_type == "BI" else None,
        query_passport=payload.id_number.strip() if payload.id_type == "PASSPORT" else None,
        status=RiskStatus.DONE,
        matches=[],
        score="0" if is_no_match else None,
        summary="Sem correspondência nas fontes disponíveis." if is_no_match else None,
    )
    db.add(risk)
    db.commit()
    db.refresh(risk)
    return RiskOut.model_validate(risk)


@router.get("", response_model=list[RiskOut])
def list_risks(db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(Risk)
    role_val = getattr(getattr(user, "role", None), "value", getattr(user, "role", None))
    if role_val != "SUPER_ADMIN":
        q = q.filter(Risk.entity_id == user.entity_id)
    items = q.order_by(Risk.created_at.desc()).limit(200).all()
    return [RiskOut.model_validate(r) for r in items]


@router.get("/{risk_id}", response_model=RiskOut)
def get_risk(risk_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    risk = db.query(Risk).filter(Risk.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk não encontrado")
    _ensure_scope(user, risk.entity_id)
    return RiskOut.model_validate(risk)


@router.get("/{risk_id}/pdf")
def get_risk_pdf(
    risk_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_perm("risk:pdf:download")),
):
    risk = db.query(Risk).filter(Risk.id == risk_id).first()
    if not risk:
        raise HTTPException(status_code=404, detail="Risk não encontrado")

    _ensure_scope(user, risk.entity_id)

    generated_at = datetime.now(timezone.utc)
    integrity_hash = make_integrity_hash(risk)
    server_signature = make_server_signature(integrity_hash)

    base_url = getattr(settings, "BASE_URL", "").rstrip("/")
    verify_url = f"{base_url}/verify/{risk.id}/{integrity_hash}" if base_url else ""

    pdf_bytes = build_risk_pdf_institutional_pt(
        risk=risk,
        analyst_name=getattr(user, "name", "Analista"),
        generated_at=generated_at,
        integrity_hash=integrity_hash,
        server_signature=server_signature,
        verify_url=verify_url,
        underwriting_by_product=None,
        compliance_by_category=None,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="risk-{risk.id}.pdf"'},
    )
