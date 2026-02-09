import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_perm, get_current_user
from ..models import Risk, RiskStatus, UserRole
from ..schemas import RiskOut, RiskSearchIn, RiskSearchOut, CandidateOut, RiskConfirmIn

router = APIRouter(prefix="/risks", tags=["risks"])

# ---- dataset mock (depois ligas às fontes reais) ----
CANDIDATES = [
    {
        "id": "cand-1",
        "full_name": "João Manuel",
        "nationality": "Angolana",
        "dob": "1980-02-11",
        "doc_type": "BI",
        "doc_full": "BI123456789AO",
        "doc_last4": "9AO",
        "sources": ["PEP Angola 2026", "Lista Interna Banco X"],
    },
    {
        "id": "cand-2",
        "full_name": "João Manuel",
        "nationality": "Portuguesa",
        "dob": "1976-10-03",
        "doc_type": "PASSPORT",
        "doc_full": "P1234567",
        "doc_last4": "4567",
        "sources": ["News Archive", "Sanctions Watchlist"],
    },
    {
        "id": "cand-3",
        "full_name": "João Manuel António",
        "nationality": "Angolana",
        "dob": "1988-05-19",
        "doc_type": "BI",
        "doc_full": "BI987654321AO",
        "doc_last4": "1AO",
        "sources": ["PEP Angola 2026"],
    },
]

def _risk_out(r: Risk) -> RiskOut:
    return RiskOut(
        id=r.id,
        entity_id=r.entity_id,
        name=r.query_name,
        bi=r.query_bi,
        passport=r.query_passport,
        nationality=r.query_nationality,
        score=r.score,
        summary=r.summary,
        matches=r.matches or [],
        status=r.status.value if hasattr(r.status, "value") else str(r.status),
    )

@router.get("", response_model=list[RiskOut])
def list_risks(db: Session = Depends(get_db), u=Depends(require_perm("risk:read"))):
    q = db.query(Risk)

    # scoping
    if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        q = q.filter(Risk.entity_id == u.entity_id)

    rows = q.order_by(Risk.created_at.desc()).all()
    return [_risk_out(r) for r in rows]

@router.get("/{risk_id}", response_model=RiskOut)
def get_risk(risk_id: str, db: Session = Depends(get_db), u=Depends(require_perm("risk:read"))):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Risk not found")

    if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN) and r.entity_id != u.entity_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return _risk_out(r)

@router.post("/search", response_model=RiskSearchOut)
def search_risks(data: RiskSearchIn, db: Session = Depends(get_db), u=Depends(require_perm("risk:create"))):
    # clientes não podem pesquisar noutra entidade
    if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN) and data.entity_id != u.entity_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    name = (data.name or "").strip().lower()
    nat = (data.nationality or "").strip().lower()

    hits = []
    for c in CANDIDATES:
        if name and name not in c["full_name"].lower():
            continue

        score = 40
        if c["full_name"].lower() == name:
            score += 20
        if nat and nat in (c.get("nationality") or "").lower():
            score += 20
        if c.get("doc_last4"):
            score += 10
        if c.get("dob"):
            score += 10
        if score > 100:
            score = 100

        hits.append(
            CandidateOut(
                id=c["id"],
                full_name=c["full_name"],
                nationality=c.get("nationality"),
                dob=c.get("dob"),
                doc_type=c.get("doc_type"),
                doc_last4=c.get("doc_last4"),
                sources=c.get("sources", []),
                match_score=score,
            )
        )

    hits.sort(key=lambda x: x.match_score, reverse=True)

    return {
        "disambiguation_required": len(hits) > 1,
        "candidates": hits,
    }

@router.post("/confirm", response_model=RiskOut)
def confirm_risk(data: RiskConfirmIn, db: Session = Depends(get_db), u=Depends(require_perm("risk:confirm"))):
    # clientes não podem confirmar noutra entidade
    if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN) and data.entity_id != u.entity_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    cand = next((c for c in CANDIDATES if c["id"] == data.candidate_id), None)
    if not cand:
        raise HTTPException(status_code=400, detail="Candidate not found")

    # valida doc (mock)
    if data.id_type == "BI" and not data.id_number.upper().startswith("BI"):
        raise HTTPException(status_code=400, detail="Invalid BI")
    if data.id_type == "PASSPORT" and len(data.id_number.strip()) < 5:
        raise HTTPException(status_code=400, detail="Invalid passport")

    is_pep = any("pep" in s.lower() for s in cand.get("sources", []))
    score = "HIGH" if is_pep else "LOW"
    summary = "Resultado gerado (mock). Pronto para ligar a fontes reais."

    r = Risk(
        id=str(uuid.uuid4()),
        entity_id=data.entity_id,
        query_name=data.name,
        query_nationality=data.nationality,
        query_bi=data.id_number if data.id_type == "BI" else None,
        query_passport=data.id_number if data.id_type == "PASSPORT" else None,
        score=score,
        summary=summary,
        matches=[{
            "candidate_id": cand["id"],
            "full_name": cand["full_name"],
            "sources": cand.get("sources", []),
            "is_pep": is_pep,
        }],
        status=RiskStatus.DONE,
        created_by=u.id,
    )

    db.add(r)
    db.commit()

    return _risk_out(r)
