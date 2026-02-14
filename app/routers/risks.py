from __future__ import annotations

import uuid
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.audit import log
from app.db import get_db
from app.deps import require_perm
from app.models import Risk, RiskStatus, User, UserRole
from app.schemas import CandidateOut, RiskConfirmIn, RiskOut, RiskSearchIn, RiskSearchOut
from app.settings import settings
from app.pdfs import build_risk_pdf_institutional, make_integrity_hash, make_server_signature

router = APIRouter(prefix="/risks", tags=["risks"])


# -------------------------
# Multi-tenant utilities
# -------------------------
def _resolve_entity_id(u: User, requested: str | None) -> str:
    if u.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        if not requested:
            raise HTTPException(status_code=400, detail="entity_id required for admins")
        return requested
    if not u.entity_id:
        raise HTTPException(status_code=400, detail="User entity_id missing")
    return u.entity_id


def _guard_risk_scope(u: User, r: Risk):
    if u.entity_id and r.entity_id != u.entity_id:
        raise HTTPException(status_code=404, detail="Risk not found")


def _risk_to_out(r: Risk) -> RiskOut:
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
        status=getattr(r.status, "value", str(r.status)),
    )


# -------------------------
# Underwriting SQL (auto-detect)
# -------------------------
def _table_exists(db: Session, table: str) -> bool:
    q = text(
        """
        SELECT EXISTS (
          SELECT 1
          FROM information_schema.tables
          WHERE table_schema = 'public' AND table_name = :t
        ) AS ok
        """
    )
    return bool(db.execute(q, {"t": table}).scalar())


def _column_exists(db: Session, table: str, col: str) -> bool:
    q = text(
        """
        SELECT EXISTS (
          SELECT 1
          FROM information_schema.columns
          WHERE table_schema = 'public' AND table_name = :t AND column_name = :c
        ) AS ok
        """
    )
    return bool(db.execute(q, {"t": table, "c": col}).scalar())


def _pick_first_existing_table(db: Session, candidates: list[str]) -> Optional[str]:
    for t in candidates:
        if _table_exists(db, t):
            return t
    return None


def _pick_first_existing_column(db: Session, table: str, candidates: list[str]) -> Optional[str]:
    for c in candidates:
        if _column_exists(db, table, c):
            return c
    return None


def _underwriting_rollup_sql(db: Session, entity_id: str) -> Dict[str, Any]:
    """
    Lê underwriting por SQL puro e agrupa por product_type.
    Não depende de nomes de models Python.

    Espera (idealmente):
      - tabela policies: insurance_policies (ou variações)
      - colunas: entity_id, product_type, id (ou policy_id)
    E tenta ligar pagamentos/sinistros/cancelamentos/fraud flags por policy_id quando existirem.
    """
    # 1) achar tabela de apólices
    policies_table = _pick_first_existing_table(
        db,
        [
            "insurance_policies",
            "policies",
            "underwriting_policies",
            "insurance_policy",
            "policy",
        ],
    )
    if not policies_table:
        return {"_meta": {"reason": "no_policies_table_found"}}

    # 2) colunas chave
    eid_col = _pick_first_existing_column(db, policies_table, ["entity_id", "tenant_id", "entity"])
    pt_col = _pick_first_existing_column(db, policies_table, ["product_type", "insurance_type", "branch", "product"])
    pid_col = _pick_first_existing_column(db, policies_table, ["id", "policy_id", "policy_uuid"])

    if not eid_col or not pt_col or not pid_col:
        return {
            "_meta": {
                "reason": "missing_required_columns",
                "policies_table": policies_table,
                "entity_col": eid_col,
                "product_type_col": pt_col,
                "policy_id_col": pid_col,
            }
        }

    # 3) fetch policies (limit alto mas controlado)
    pol_rows = db.execute(
        text(
            f"""
            SELECT {pid_col} AS policy_id,
                   COALESCE({pt_col}, 'N/A') AS product_type
            FROM {policies_table}
            WHERE {eid_col} = :eid
            """
        ),
        {"eid": entity_id},
    ).mappings().all()

    if not pol_rows:
        return {
            "_meta": {
                "reason": "no_policy_rows_for_entity",
                "policies_table": policies_table,
            }
        }

    # index policies by product_type
    by_pt: Dict[str, Any] = {}
    policy_ids: list[str] = []
    for r in pol_rows:
        pt = str(r["product_type"] or "N/A")
        by_pt.setdefault(pt, {"policies": 0, "payments": 0, "claims": 0, "cancellations": 0, "fraud_flags": 0})
        by_pt[pt]["policies"] += 1
        policy_ids.append(str(r["policy_id"]))

    # helpers to count by table if exists
    def count_related(table_candidates: list[str], policy_fk_candidates: list[str]) -> Dict[str, int]:
        t = _pick_first_existing_table(db, table_candidates)
        if not t:
            return {}
        fk = _pick_first_existing_column(db, t, policy_fk_candidates)
        if not fk:
            return {}

        # contamos por product_type usando JOIN na tabela policies
        rows = db.execute(
            text(
                f"""
                SELECT COALESCE(p.{pt_col}, 'N/A') AS product_type, COUNT(*) AS n
                FROM {t} x
                JOIN {policies_table} p ON p.{pid_col} = x.{fk}
                WHERE p.{eid_col} = :eid
                GROUP BY COALESCE(p.{pt_col}, 'N/A')
                """
            ),
            {"eid": entity_id},
        ).mappings().all()

        return {str(rr["product_type"]): int(rr["n"]) for rr in rows}

    payments = count_related(["payments", "policy_payments", "insurance_payments"], ["policy_id", "insurance_policy_id", "policy_uuid"])
    claims = count_related(["claims", "policy_claims", "insurance_claims"], ["policy_id", "insurance_policy_id", "policy_uuid"])
    cancellations = count_related(["cancellations", "policy_cancellations"], ["policy_id", "insurance_policy_id", "policy_uuid"])
    fraud_flags = count_related(["fraud_flags", "fraud", "policy_fraud_flags"], ["policy_id", "insurance_policy_id", "policy_uuid"])

    for pt, n in (payments or {}).items():
        by_pt.setdefault(pt, {"policies": 0, "payments": 0, "claims": 0, "cancellations": 0, "fraud_flags": 0})
        by_pt[pt]["payments"] = n
    for pt, n in (claims or {}).items():
        by_pt.setdefault(pt, {"policies": 0, "payments": 0, "claims": 0, "cancellations": 0, "fraud_flags": 0})
        by_pt[pt]["claims"] = n
    for pt, n in (cancellations or {}).items():
        by_pt.setdefault(pt, {"policies": 0, "payments": 0, "claims": 0, "cancellations": 0, "fraud_flags": 0})
        by_pt[pt]["cancellations"] = n
    for pt, n in (fraud_flags or {}).items():
        by_pt.setdefault(pt, {"policies": 0, "payments": 0, "claims": 0, "cancellations": 0, "fraud_flags": 0})
        by_pt[pt]["fraud_flags"] = n

    return {
        "_meta": {
            "policies_table": policies_table,
            "entity_col": eid_col,
            "product_type_col": pt_col,
            "policy_id_col": pid_col,
            "related_tables": {
                "payments": bool(payments),
                "claims": bool(claims),
                "cancellations": bool(cancellations),
                "fraud_flags": bool(fraud_flags),
            },
        },
        "by_product_type": by_pt,
    }


# -------------------------
# Endpoints
# -------------------------
@router.get("", response_model=list[RiskOut])
def list_risks(db: Session = Depends(get_db), u: User = Depends(require_perm("risk:read"))):
    q = db.query(Risk)
    if u.entity_id:
        q = q.filter(Risk.entity_id == u.entity_id)
    rows = q.order_by(Risk.created_at.desc()).limit(200).all()
    return [_risk_to_out(r) for r in rows]


@router.get("/{risk_id}", response_model=RiskOut)
def get_risk(risk_id: str, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:read"))):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Risk not found")
    _guard_risk_scope(u, r)
    return _risk_to_out(r)


@router.post("/search", response_model=RiskSearchOut)
def search_risk(body: RiskSearchIn, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:create"))):
    entity_id = _resolve_entity_id(u, body.entity_id)

    base = (body.name or "").strip()
    if not base:
        raise HTTPException(status_code=400, detail="name is required")

    candidates: list[CandidateOut] = []
    for i in range(1, 4):
        candidates.append(
            CandidateOut(
                id=str(uuid.uuid4()),
                full_name=f"{base} {i}",
                nationality=body.nationality,
                dob=None,
                doc_type=None,
                doc_last4=None,
                sources=["PEP (interno)", "Sanções (interno)", "Watchlists (interno)"],
                match_score=90 - (i * 7),
            )
        )

    log(db, "RISK_SEARCH", actor=u, entity=None, target_ref=base, meta={"entity_id": entity_id})
    return RiskSearchOut(disambiguation_required=True, candidates=candidates)


@router.post("/confirm", response_model=RiskOut)
def confirm_risk(body: RiskConfirmIn, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:confirm"))):
    entity_id = _resolve_entity_id(u, body.entity_id)

    pep_hits = []
    try:
        from app.services.compliance_matching import pep_match  # type: ignore

        pep_hits = pep_match(
            db=db,
            entity_id=entity_id,
            full_name=body.name,
            bi=body.id_number if body.id_type == "BI" else None,
            passport=body.id_number if body.id_type == "PASSPORT" else None,
        )
    except Exception:
        pep_hits = []

    base_score = 50
    if pep_hits:
        base_score = 85

    score_int = int(base_score)
    score = str(score_int)

    summary = "Avaliação preliminar com base nas fontes configuradas e dados fornecidos."
    if pep_hits:
        summary = "Foram identificadas correspondências PEP. Recomenda-se revisão reforçada (EDD) e validação documental."

    r = Risk(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        query_name=body.name,
        query_nationality=body.nationality,
        query_bi=body.id_number if body.id_type == "BI" else None,
        query_passport=body.id_number if body.id_type == "PASSPORT" else None,
        score=score,
        summary=summary,
        matches=pep_hits,
        status=RiskStatus.DONE,
        created_by=u.id,
        created_at=datetime.utcnow(),
    )
    db.add(r)
    db.commit()

    log(db, "RISK_CONFIRM", actor=u, entity=None, target_ref=r.id, meta={"entity_id": entity_id, "score": score_int})
    return _risk_to_out(r)


@router.get("/{risk_id}/pdf")
def risk_pdf(risk_id: str, db: Session = Depends(get_db), u: User = Depends(require_perm("risk:pdf:download"))):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Risk not found")
    _guard_risk_scope(u, r)

    integrity_hash = make_integrity_hash(r)
    verify_url = f"{settings.BASE_URL}/verify/{r.id}/{integrity_hash}"
    server_signature = make_server_signature(integrity_hash)

    # Compliance normalized (sem falhar)
    compliance_by_category = None
    try:
        from app.pdfs import _normalize_matches_generic  # type: ignore

        compliance_by_category = _normalize_matches_generic(getattr(r, "matches", None) or [])
    except Exception:
        compliance_by_category = None

    # Underwriting: SQL auto-detect (não depende de models)
    uw_pack = _underwriting_rollup_sql(db, r.entity_id)

    underwriting_by_product = None
    meta = uw_pack.get("_meta", {}) if isinstance(uw_pack, dict) else {}
    by_pt = uw_pack.get("by_product_type") if isinstance(uw_pack, dict) else None

    if isinstance(by_pt, dict) and by_pt:
        # formato esperado pelo pdf builder
        underwriting_by_product = {
            pt: {
                "policies": [1] * int(v.get("policies", 0)),
                "payments": [1] * int(v.get("payments", 0)),
                "claims": [1] * int(v.get("claims", 0)),
                "cancellations": [1] * int(v.get("cancellations", 0)),
                "fraud_flags": [1] * int(v.get("fraud_flags", 0)),
            }
            for pt, v in by_pt.items()
        }
    else:
        underwriting_by_product = None

    # Log técnico (para sabermos se é falta de dados ou falta de tabela/coluna)
    log(
        db,
        "UNDERWRITING_ROLLUP",
        actor=u,
        entity=None,
        target_ref=r.id,
        meta={"entity_id": r.entity_id, "meta": meta, "has_data": bool(underwriting_by_product)},
    )

    try:
        pdf_bytes = build_risk_pdf_institutional(
            risk=r,
            analyst_name=u.name,
            generated_at=datetime.utcnow(),
            integrity_hash=integrity_hash,
            server_signature=server_signature,
            verify_url=verify_url,
            underwriting_by_product=underwriting_by_product,
            compliance_by_category=compliance_by_category,
            report_title="Relatório Institucional de Risco",
            report_version="v1.1",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {type(e).__name__}: {e}")

    log(db, "RISK_PDF_DOWNLOAD", actor=u, entity=None, target_ref=r.id, meta={"entity_id": r.entity_id, "hash": integrity_hash})

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=risk_{r.id}.pdf"},
    )
