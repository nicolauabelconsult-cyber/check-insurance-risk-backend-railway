from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import InsurancePolicy, Payment, Claim, Cancellation, FraudFlag


def _clean(row: Any) -> dict:
    d = dict(getattr(row, "__dict__", {}) or {})
    d.pop("_sa_instance_state", None)
    return d


def _match_subject(model, full_name: Optional[str], bi: Optional[str], passport: Optional[str]):
    clauses = []

    if bi and hasattr(model, "subject_bi"):
        clauses.append(model.subject_bi == bi)
    if passport and hasattr(model, "subject_passport"):
        clauses.append(model.subject_passport == passport)

    # fallback por nome (quando não existe BI/passaporte)
    if full_name and hasattr(model, "subject_full_name"):
        clauses.append(model.subject_full_name.ilike(f"%{full_name}%"))

    # se não houver nada, devolve True-ish (mas normalmente não queremos isso)
    return or_(*clauses) if clauses else None


def load_underwriting_by_product(
    db: Session,
    entity_id: str,
    full_name: Optional[str] = None,
    bi: Optional[str] = None,
    passport: Optional[str] = None,
) -> Dict[str, Dict[str, list]]:
    """
    Devolve underwriting agrupado por product_type:
    {
      "AUTO": {"policies":[...], "payments":[...], "claims":[...], "cancellations":[...], "fraud_flags":[...]},
      "SAUDE": {...}
    }
    """
    buckets = defaultdict(lambda: {
        "policies": [],
        "payments": [],
        "claims": [],
        "cancellations": [],
        "fraud_flags": [],
    })

    def fetch(model, key: str, limit: int = 200):
        q = db.query(model).filter(model.entity_id == entity_id)
        clause = _match_subject(model, full_name, bi, passport)
        if clause is not None:
            q = q.filter(clause)
        rows = q.limit(limit).all()
        for row in rows or []:
            d = _clean(row)
            pt = (d.get("product_type") or "N/A")
            buckets[str(pt)][key].append(d)

    fetch(InsurancePolicy, "policies")
    fetch(Payment, "payments")
    fetch(Claim, "claims")
    fetch(Cancellation, "cancellations")
    fetch(FraudFlag, "fraud_flags")

    out = dict(buckets)
    # remove vazios
    out = {pt: pack for pt, pack in out.items() if any((pack[k] for k in pack))}
    return out
