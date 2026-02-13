from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_perm
from app.models import User, UserRole
from app.audit import log

from app.insurance_models import (
    InsurancePayment,
    InsuranceClaim,
    InsurancePolicy,
    InsuranceCancellation,
    InsuranceFraudFlag,
)

router = APIRouter(prefix="/insurance", tags=["insurance"])


def _resolve_entity_id(u: User, requested: str | None) -> str:
    if u.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        if not requested:
            raise HTTPException(status_code=400, detail="entity_id required for admins")
        return requested
    if not u.entity_id:
        raise HTTPException(status_code=400, detail="User entity_id missing")
    return u.entity_id


# -------------------------
# Schemas (JSON bulk)
# -------------------------

class PaymentIn(BaseModel):
    entity_id: str | None = None
    bi: str | None = None
    passport: str | None = None
    full_name: str | None = None
    due_date: date | None = None
    paid_date: date | None = None
    amount: int | None = None
    is_paid: bool = False


class ClaimIn(BaseModel):
    entity_id: str | None = None
    bi: str | None = None
    passport: str | None = None
    full_name: str | None = None
    claim_date: date | None = None
    claim_type: str | None = None
    amount_paid: int | None = None
    amount_reserved: int | None = None
    status: str | None = None
    note: str | None = None


class PolicyIn(BaseModel):
    entity_id: str | None = None
    bi: str | None = None
    passport: str | None = None
    full_name: str | None = None
    policy_no: str
    product_type: str | None = None
    status: str | None = "ACTIVE"
    start_date: date | None = None
    end_date: date | None = None
    premium: int | None = None
    sum_insured: int | None = None


class CancellationIn(BaseModel):
    entity_id: str | None = None
    bi: str | None = None
    passport: str | None = None
    full_name: str | None = None
    policy_no: str | None = None
    date: date | None = None
    reason: str | None = None


class FraudFlagIn(BaseModel):
    entity_id: str | None = None
    bi: str | None = None
    passport: str | None = None
    full_name: str | None = None
    flag: str
    severity: str | None = None
    note: str | None = None
    date: date | None = None


# -------------------------
# Bulk endpoints
# -------------------------

@router.post("/payments/bulk")
def upload_payments(items: list[PaymentIn], db: Session = Depends(get_db), u: User = Depends(require_perm("insurance:upload"))):
    inserted = 0
    for it in items:
        entity_id = _resolve_entity_id(u, it.entity_id)
        row = InsurancePayment(
            id=str(uuid.uuid4()),
            entity_id=entity_id,
            bi=it.bi,
            passport=it.passport,
            full_name=it.full_name,
            due_date=it.due_date,
            paid_date=it.paid_date,
            amount=it.amount,
            is_paid=it.is_paid,
        )
        db.add(row)
        inserted += 1

    db.commit()
    log(db, "INSURANCE_PAYMENTS_UPLOAD", actor=u, entity=None, target_ref=str(inserted), meta={"rows": inserted})
    return {"inserted": inserted}


@router.post("/claims/bulk")
def upload_claims(items: list[ClaimIn], db: Session = Depends(get_db), u: User = Depends(require_perm("insurance:upload"))):
    inserted = 0
    for it in items:
        entity_id = _resolve_entity_id(u, it.entity_id)
        row = InsuranceClaim(
            id=str(uuid.uuid4()),
            entity_id=entity_id,
            bi=it.bi,
            passport=it.passport,
            full_name=it.full_name,
            claim_date=it.claim_date,
            claim_type=it.claim_type,
            amount_paid=it.amount_paid,
            amount_reserved=it.amount_reserved,
            status=it.status,
            note=it.note,
        )
        db.add(row)
        inserted += 1

    db.commit()
    log(db, "INSURANCE_CLAIMS_UPLOAD", actor=u, entity=None, target_ref=str(inserted), meta={"rows": inserted})
    return {"inserted": inserted}


@router.post("/policies/bulk")
def upload_policies(items: list[PolicyIn], db: Session = Depends(get_db), u: User = Depends(require_perm("insurance:upload"))):
    inserted = 0
    for it in items:
        entity_id = _resolve_entity_id(u, it.entity_id)
        row = InsurancePolicy(
            id=str(uuid.uuid4()),
            entity_id=entity_id,
            bi=it.bi,
            passport=it.passport,
            full_name=it.full_name,
            policy_no=it.policy_no,
            product_type=it.product_type,
            status=it.status,
            start_date=it.start_date,
            end_date=it.end_date,
            premium=it.premium,
            sum_insured=it.sum_insured,
        )
        db.add(row)
        inserted += 1

    db.commit()
    log(db, "INSURANCE_POLICIES_UPLOAD", actor=u, entity=None, target_ref=str(inserted), meta={"rows": inserted})
    return {"inserted": inserted}


@router.post("/cancellations/bulk")
def upload_cancellations(items: list[CancellationIn], db: Session = Depends(get_db), u: User = Depends(require_perm("insurance:upload"))):
    inserted = 0
    for it in items:
        entity_id = _resolve_entity_id(u, it.entity_id)
        row = InsuranceCancellation(
            id=str(uuid.uuid4()),
            entity_id=entity_id,
            bi=it.bi,
            passport=it.passport,
            full_name=it.full_name,
            policy_no=it.policy_no,
            date=it.date,
            reason=it.reason,
        )
        db.add(row)
        inserted += 1

    db.commit()
    log(db, "INSURANCE_CANCELLATIONS_UPLOAD", actor=u, entity=None, target_ref=str(inserted), meta={"rows": inserted})
    return {"inserted": inserted}


@router.post("/fraud/bulk")
def upload_fraud(items: list[FraudFlagIn], db: Session = Depends(get_db), u: User = Depends(require_perm("insurance:upload"))):
    inserted = 0
    for it in items:
        entity_id = _resolve_entity_id(u, it.entity_id)
        row = InsuranceFraudFlag(
            id=str(uuid.uuid4()),
            entity_id=entity_id,
            bi=it.bi,
            passport=it.passport,
            full_name=it.full_name,
            flag=it.flag,
            severity=it.severity,
            note=it.note,
            date=it.date,
        )
        db.add(row)
        inserted += 1

    db.commit()
    log(db, "INSURANCE_FRAUD_UPLOAD", actor=u, entity=None, target_ref=str(inserted), meta={"rows": inserted})
    return {"inserted": inserted}
