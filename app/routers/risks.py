import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_perm, get_current_user
from ..models import Risk, Entity  # ajusta conforme teus models
from ..schemas import (
    RiskOut,
    RiskCreate,
    RiskSearchIn,
    RiskSearchOut,
    CandidateOut,
    RiskConfirmIn,
)
from ..audit import log
from ..pdfs import build_risk_pdf  # já tens

router = APIRouter(prefix="/risks", tags=["risks"])

# ----------------------------
# MOCK DATASET (candidatos)
# Depois ligamos a fontes reais (PEP/OFAC/etc)
# ----------------------------
CANDIDATES = [
    {
        "id": "cand-1",
        "full_name": "João Manuel",
        "nationality": "Angolana",
        "dob": "1980-02-11",
        "doc_type": "BI",
        "doc_full": "BI123456789AO",
        "sources": ["PEP Angola 2026", "Lista Interna Banco X"],
    },
    {
        "id": "cand-2",
        "full_name": "João Manuel",
        "nationality": "Portuguesa",
        "dob": "1976-10-03",
        "doc_type": "PASSPORT",
        "doc_full": "P1234567",
        "sources": ["News Archive", "Sanctions Watchlist"],
    },
    {
        "id": "cand-3",
        "full_name": "João Manuel António",
        "nationality": "Angolana",
        "dob": "1988-05-19",
        "doc_type": "BI",
        "doc_full": "BI987654321AO",
        "sources": ["PEP Angola 2026"],
    },
]

def _score_candidate(name: str, nationality: str | None, c: dict) -> int:
    q = (name or "").strip().lower()
    nat = (nationality or "").strip().lower()

    full = (c.get("full_name") or "").lower()
    c_nat = (c.get("nationality") or "").lower()

    score = 0
    if full == q:
        score += 60
    elif q and q in full:
        score += 40

    if nat and nat in c_nat:
        score += 20

    if c.get("doc_type") and c.get("doc_full"):
        score += 10
    if c.get("dob"):
        score += 10

    return min(score, 100)

# ----------------------------
# 1) SEARCH (desambiguação)
# ----------------------------
@router.post("/search", response_model=RiskSearchOut)
def search_candidates(
    body: RiskSearchIn,
    db: Session = Depends(get_db),
    u=Depends(require_perm("risk:create")),
):
    # valida entity
    ent = db.get(Entity, body.entity_id)
    if not ent:
        raise HTTPException(status_code=400, detail="Invalid entity_id")

    # clientes não podem pesquisar noutra entidade
    if getattr(u, "entity_id", None) and u.entity_id != body.entity_id and u.role not in ("SUPER_ADMIN", "ADMIN"):
        raise HTTPException(status_code=403, detail="Forbidden")

    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    hits = []
    for c in CANDIDATES:
        sc = _score_candidate(name, body.nationality, c)
        # filtro mínimo
        if sc >= 40:
            doc_full = c.get("doc_full") or ""
            hits.append(
                CandidateOut(
                    id=c["id"],
                    full_name=c["full_name"],
                    nationality=c.get("nationality"),
                    dob=c.get("dob"),
                    doc_type=c.get("doc_type"),
                    doc_last4=doc_full[-4:] if doc_full else None,
                    sources=c.get("sources", []),
                    match_score=sc,
                )
            )

    hits.sort(key=lambda x: x.match_score, reverse=True)

    # se tiver 0-1 resultados -> não precisa desambiguar
    disambiguation = len(hits) > 1

    log(db, "RISK_SEARCH", actor=u, entity=ent, target_ref=name, meta={"results": len(hits)})

    return RiskSearchOut(disambiguation_required=disambiguation, candidates=hits)

# ----------------------------
# 2) CONFIRM + CREATE FINAL
# ----------------------------
@router.post("/confirm", response_model=RiskOut)
def confirm_and_create(
    body: RiskConfirmIn,
    db: Session = Depends(get_db),
    u=Depends(require_perm("risk:create")),
):
    ent = db.get(Entity, body.entity_id)
    if not ent:
        raise HTTPException(status_code=400, detail="Invalid entity_id")

    # segurança: scope
    if getattr(u, "entity_id", None) and u.entity_id != body.entity_id and u.role not in ("SUPER_ADMIN", "ADMIN"):
        raise HTTPException(status_code=403, detail="Forbidden")

    # valida candidato
    cand = next((c for c in CANDIDATES if c["id"] == body.candidate_id), None)
    if not cand:
        raise HTTPException(status_code=400, detail="Invalid candidate_id")

    # valida doc forte
    if not body.id_number.strip():
        raise HTTPException(status_code=400, detail="id_number required")

    # score/risk mock (já alinhado ao que combinámos)
    is_pep = any("pep" in (s or "").lower() for s in cand.get("sources", []))
    score = "HIGH" if is_pep else "LOW"
    summary = "Resultado gerado. Pronto para ligar a fontes reais."

    # cria risk (ajusta campos conforme teu model Risk)
    r = Risk(
        id=str(uuid.uuid4()),
        entity_id=ent.id,
        name=body.name.strip(),
        nationality=body.nationality.strip(),
        bi=body.id_number.strip() if body.id_type == "BI" else None,
        passport=body.id_number.strip() if body.id_type == "PASSPORT" else None,
        score=score,
        summary=summary,
        matches=[],  # podes guardar lista de fontes/matches depois
        status="DONE",
    )

    db.add(r)
    db.commit()
    db.refresh(r)

    log(
        db,
        "RISK_CREATED",
        actor=u,
        entity=ent,
        target_ref=r.id,
        meta={"candidate_id": body.candidate_id, "score": score},
    )

    return RiskOut(
        id=r.id,
        entity_id=r.entity_id,
        name=r.name,
        bi=getattr(r, "bi", None),
        passport=getattr(r, "passport", None),
        nationality=r.nationality,
        score=r.score,
        summary=r.summary,
        matches=r.matches or [],
        status=r.status,
    )

# ----------------------------
# 3) PDF
# ----------------------------
@router.get("/{risk_id}/pdf")
def download_pdf(
    risk_id: str,
    db: Session = Depends(get_db),
    u=Depends(require_perm("risk:pdf:download")),
):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Not found")

    # scope
    if getattr(u, "entity_id", None) and u.entity_id != r.entity_id and u.role not in ("SUPER_ADMIN", "ADMIN"):
        raise HTTPException(status_code=403, detail="Forbidden")

    pdf_bytes = build_risk_pdf(r)  # deve devolver bytes
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="RISK-{risk_id}.pdf"'},
    )
