import uuid
from difflib import SequenceMatcher
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_perm
from ..models import Risk, RiskStatus
from ..schemas import RiskCreate, RiskOut, RiskSearchOut
from ..audit import log
from ..pdfs import build_risk_pdf

router = APIRouter(prefix="/risks", tags=["risks"])

def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()

# MOCK de base de pessoas (depois liga a fontes reais)
MOCK_PERSONS = [
    {"id": "p1", "name": "João Manuel Silva", "bi": "123456789LA034", "passport": "P1234567", "nationality": "AO"},
    {"id": "p2", "name": "João Manuel Silva", "bi": "987654321LA012", "passport": "P7654321", "nationality": "AO"},
    {"id": "p3", "name": "Joana Maria Silva", "bi": "555666777LA000", "passport": "P0001122", "nationality": "AO"},
]

@router.post("/search", response_model=RiskSearchOut)
def search(payload: RiskCreate, db: Session = Depends(get_db), u=Depends(require_perm("risk:create"))):
    # pesquisa por BI / Passaporte é “quase único”
    if payload.bi:
        hits = [p for p in MOCK_PERSONS if p["bi"] == payload.bi]
        return {"disambiguation_required": False, "candidates": hits}

    if payload.passport:
        hits = [p for p in MOCK_PERSONS if p["passport"] == payload.passport]
        return {"disambiguation_required": False, "candidates": hits}

    # nome + nacionalidade (pode dar vários)
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name or bi or passport required")

    candidates = []
    for p in MOCK_PERSONS:
        if payload.nationality and p["nationality"] != payload.nationality:
            continue
        score = _sim(name, p["name"])
        if score >= 0.70:  # threshold
            candidates.append({**p, "match_score": round(score, 3)})

    candidates.sort(key=lambda x: x.get("match_score", 0), reverse=True)

    if len(candidates) == 0:
        return {"disambiguation_required": False, "candidates": []}

    if len(candidates) == 1:
        return {"disambiguation_required": False, "candidates": candidates}

    return {"disambiguation_required": True, "candidates": candidates}

@router.post("", response_model=RiskOut)
def create_risk(payload: RiskCreate, db: Session = Depends(get_db), u=Depends(require_perm("risk:create"))):
    entity_id = payload.entity_id or u.entity_id
    if not entity_id:
        raise HTTPException(status_code=400, detail="entity_id required")

    # Se veio com selected_candidate_id (do frontend)
    selected = None
    if payload.selected_candidate_id:
        selected = next((p for p in MOCK_PERSONS if p["id"] == payload.selected_candidate_id), None)
        if not selected:
            raise HTTPException(status_code=400, detail="Invalid selected_candidate_id")

    # Se não selecionou e é pesquisa por nome, valida disambiguation
    if payload.name and not payload.selected_candidate_id and not payload.bi and not payload.passport:
        # reusa lógica para decidir se precisa desambiguar
        res = search(payload, db, u)
        if res["disambiguation_required"]:
            raise HTTPException(status_code=409, detail={"message": "Multiple matches, select one", "candidates": res["candidates"]})
        selected = res["candidates"][0] if res["candidates"] else None

    # Calcula score (mock)
    matches = []
    if selected:
        matches = [selected]

    score = "LOW"
    if matches:
        score = "MEDIUM"  # placeholder

    r = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        query_name=payload.name,
        query_bi=payload.bi,
        query_passport=payload.passport,
        query_nationality=payload.nationality,
        score=score,
        summary="Resultado gerado (mock). Pronto para ligar a fontes reais.",
        matches=matches,
        status=RiskStatus.DONE,
        created_by=u.id,
    )
    db.add(r)
    db.commit()

    log(db, "RISK_CREATED", actor=u, entity=None, target_ref=r.id, meta={"score": score, "entity_id": entity_id})
    return RiskOut(
        id=r.id, entity_id=r.entity_id,
        name=r.query_name, bi=r.query_bi, passport=r.query_passport, nationality=r.query_nationality,
        score=r.score, summary=r.summary, matches=r.matches, status=r.status.value
    )

@router.get("", response_model=list[RiskOut])
def list_risks(db: Session = Depends(get_db), u=Depends(require_perm("risk:read"))):
    q = db.query(Risk)
    if u.entity_id:
        q = q.filter(Risk.entity_id == u.entity_id)
    items = q.order_by(Risk.created_at.desc()).limit(100).all()
    return [RiskOut(
        id=r.id, entity_id=r.entity_id,
        name=r.query_name, bi=r.query_bi, passport=r.query_passport, nationality=r.query_nationality,
        score=r.score, summary=r.summary, matches=r.matches, status=r.status.value
    ) for r in items]

@router.get("/{risk_id}", response_model=RiskOut)
def get_risk(risk_id: str, db: Session = Depends(get_db), u=Depends(require_perm("risk:read"))):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Not found")
    if u.entity_id and r.entity_id != u.entity_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return RiskOut(
        id=r.id, entity_id=r.entity_id,
        name=r.query_name, bi=r.query_bi, passport=r.query_passport, nationality=r.query_nationality,
        score=r.score, summary=r.summary, matches=r.matches, status=r.status.value
    )

@router.get("/{risk_id}/pdf")
def risk_pdf(risk_id: str, db: Session = Depends(get_db), u=Depends(require_perm("risk:pdf:download"))):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Not found")
    if u.entity_id and r.entity_id != u.entity_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    pdf = build_risk_pdf(
        "Check Insurance Risk - Relatório",
        {
            "Risk ID": r.id,
            "Entidade": r.entity_id,
            "Nome": r.query_name,
            "BI": r.query_bi,
            "Passaporte": r.query_passport,
            "Nacionalidade": r.query_nationality,
            "Score": r.score,
            "Resumo": r.summary,
            "Matches": str(r.matches),
        },
    )
    log(db, "RISK_PDF_DOWNLOADED", actor=u, entity=None, target_ref=r.id)
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=risk_{r.id}.pdf"})
