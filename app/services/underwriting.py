from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.models import InsurancePolicy, Payment, Claim, Cancellation, FraudFlag


def _norm(v: Optional[str]) -> str:
    return (v or "").strip().lower()


def _serialize_policy(row: InsurancePolicy) -> dict:
    return {
        "id": row.id,
        "subject_full_name": row.subject_full_name,
        "subject_bi": row.subject_bi,
        "subject_passport": row.subject_passport,
        "product_type": row.product_type,
        "policy_number": row.policy_number,
        "insurer_name": row.insurer_name,
        "status": row.status,
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "currency": row.currency,
        "premium_amount": row.premium_amount,
        "sum_insured": row.sum_insured,
        "source_name": row.source_name,
        "source_ref": row.source_ref,
        "raw_payload": row.raw_payload,
    }


def _serialize_payment(row: Payment) -> dict:
    return {
        "id": row.id,
        "subject_full_name": row.subject_full_name,
        "subject_bi": row.subject_bi,
        "subject_passport": row.subject_passport,
        "product_type": row.product_type,
        "policy_number": row.policy_number,
        "amount": row.amount,
        "currency": row.currency,
        "paid_at": row.paid_at.isoformat() if row.paid_at else None,
        "due_at": row.due_at.isoformat() if row.due_at else None,
        "status": row.status,
        "source_name": row.source_name,
        "source_ref": row.source_ref,
        "raw_payload": row.raw_payload,
    }


def _serialize_claim(row: Claim) -> dict:
    return {
        "id": row.id,
        "subject_full_name": row.subject_full_name,
        "subject_bi": row.subject_bi,
        "subject_passport": row.subject_passport,
        "product_type": row.product_type,
        "policy_number": row.policy_number,
        "claim_number": row.claim_number,
        "loss_date": row.loss_date.isoformat() if row.loss_date else None,
        "reported_at": row.reported_at.isoformat() if row.reported_at else None,
        "status": row.status,
        "amount_claimed": row.amount_claimed,
        "amount_paid": row.amount_paid,
        "currency": row.currency,
        "source_name": row.source_name,
        "source_ref": row.source_ref,
        "raw_payload": row.raw_payload,
    }


def _serialize_cancellation(row: Cancellation) -> dict:
    return {
        "id": row.id,
        "subject_full_name": row.subject_full_name,
        "subject_bi": row.subject_bi,
        "subject_passport": row.subject_passport,
        "product_type": row.product_type,
        "policy_number": row.policy_number,
        "cancelled_at": row.cancelled_at.isoformat() if row.cancelled_at else None,
        "reason": row.reason,
        "source_name": row.source_name,
        "source_ref": row.source_ref,
        "raw_payload": row.raw_payload,
    }


def _serialize_fraud(row: FraudFlag) -> dict:
    return {
        "id": row.id,
        "subject_full_name": row.subject_full_name,
        "subject_bi": row.subject_bi,
        "subject_passport": row.subject_passport,
        "product_type": row.product_type,
        "policy_number": row.policy_number,
        "flag_type": row.flag_type,
        "severity": row.severity,
        "description": row.description,
        "source_name": row.source_name,
        "source_ref": row.source_ref,
        "raw_payload": row.raw_payload,
    }


def _match_filters(model, *, full_name: Optional[str], bi: Optional[str], passport: Optional[str]):
    clauses = []

    if bi:
        clauses.append(model.subject_bi == bi.strip())

    if passport:
        clauses.append(model.subject_passport == passport.strip())

    if full_name and _norm(full_name):
        clauses.append(func.lower(func.trim(model.subject_full_name)) == _norm(full_name))

    return clauses


def _fetch_rows(
    db: Session,
    model,
    *,
    entity_id: str,
    full_name: Optional[str],
    bi: Optional[str],
    passport: Optional[str],
):
    clauses = _match_filters(model, full_name=full_name, bi=bi, passport=passport)

    if not clauses:
        return []

    return (
        db.query(model)
        .filter(model.entity_id == entity_id)
        .filter(or_(*clauses))
        .all()
    )


def load_underwriting_by_product(
    db: Session,
    *,
    entity_id: str,
    full_name: Optional[str] = None,
    bi: Optional[str] = None,
    passport: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Carrega underwriting real das tabelas:
      - insurance_policies
      - payments
      - claims
      - cancellations
      - fraud_flags

    Critério:
      1) BI exato
      2) Passaporte exato
      3) Nome exato normalizado (fallback)
    """
    policies = _fetch_rows(db, InsurancePolicy, entity_id=entity_id, full_name=full_name, bi=bi, passport=passport)
    payments = _fetch_rows(db, Payment, entity_id=entity_id, full_name=full_name, bi=bi, passport=passport)
    claims = _fetch_rows(db, Claim, entity_id=entity_id, full_name=full_name, bi=bi, passport=passport)
    cancellations = _fetch_rows(db, Cancellation, entity_id=entity_id, full_name=full_name, bi=bi, passport=passport)
    fraud_flags = _fetch_rows(db, FraudFlag, entity_id=entity_id, full_name=full_name, bi=bi, passport=passport)

    grouped: Dict[str, Any] = {}

    def ensure_bucket(product_type: Optional[str]) -> dict:
        pt = (product_type or "N/A").strip() or "N/A"
        if pt not in grouped:
            grouped[pt] = {
                "policies": [],
                "payments": [],
                "claims": [],
                "cancellations": [],
                "fraud_flags": [],
            }
        return grouped[pt]

    for row in policies:
        ensure_bucket(row.product_type)["policies"].append(_serialize_policy(row))

    for row in payments:
        ensure_bucket(row.product_type)["payments"].append(_serialize_payment(row))

    for row in claims:
        ensure_bucket(row.product_type)["claims"].append(_serialize_claim(row))

    for row in cancellations:
        ensure_bucket(row.product_type)["cancellations"].append(_serialize_cancellation(row))

    for row in fraud_flags:
        ensure_bucket(row.product_type)["fraud_flags"].append(_serialize_fraud(row))

    return grouped
