from __future__ import annotations

import uuid
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_perm
from app.models import User, UserRole
from app.audit import log

# Se já tens estes models noutro ficheiro, ajusta os imports.
# Aqui assumo que tens models de seguro já criados (insurance_payments, etc.)
from app.insurance_models import (
    InsurancePayment,
    InsuranceClaim,
    InsurancePolicy,
    InsuranceCancellation,
    InsuranceFraudFlag,
)

router = APIRouter(prefix="/insurance", tags=["insurance-sources"])


def _resolve_entity_id(u: User, requested: Optional[str]) -> str:
    if u.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        if not requested:
            raise HTTPException(status_code=400, detail="entity_id required")
        return requested
    if not u.entity_id:
        raise HTTPException(status_code=400, detail="User entity_id missing")
    return u.entity_id


class PaymentIn(BaseModel):
    entity_id: Optional[str] = None
    bi: Optional[str] = None
    passport: Optional[str] = None
    full_name: Optional[str] = None

    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    amount: Optional[int] = None
    is_paid: Optional[bool] = False


class ClaimIn(BaseModel):
    entity_id: Optional[str] = None
    bi: Optional[str] = None
    passport: Optional[str] = None
    full_name: Optional[str] = None

    claim_date: Optional[date] = None
    claim_type: Optional[str] = None
    amount_paid: Optional[int] = None
    amount_reserved: Optional[int] = None
    status: Optional[str] = None
    note: Optional[str] = None


class PolicyIn(BaseModel):
    entity_id: Optional[str] = None
    bi: Optional[str] = None
    passport: Optional[str] = None
    full_name: Optional[str] = None

    policy_no: str
    product_type: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    premium: Optional[int] = None
    sum_insured: Optional[int] = None


class CancellationIn(BaseModel):
    entity_id: Optional[str] = None
    bi: Optional[str] = None
    passport: Optional[str] = None
    full_name: Optional[str] = None

    policy_no: Optional[str] = None
    date: Optional[date] = None
    reason: Optional[str] = None


class FraudFlagIn(BaseModel):
    entity_id: Optional[str] = None
    bi: Optional[str] = None
    passport: Optional[str] = None
    full_name: Optional[str] = None

    flag: str
    severity: Optional[str] = None
    note: Optional[str] = None
    date: Optional[date] = None


@router.post("/payments/bulk")
def upload_payments_bulk(
    items: List[PaymentIn],
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("insurance:upload")),
):
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
            is_paid=bool(it.is_paid),
        )
        db.add(row)
        inserted += 1
    db.commit()
    log(db, "INSURANCE_PAYMENTS_UPLOAD", actor=u, entity=None, target_ref=str(inserted), meta={"rows": inserted})
    return {"inserted": inserted}


@router.post("/claims/bulk")
def upload_claims_bulk(
    items: List[ClaimIn],
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("insurance:upload")),
):
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
def upload_policies_bulk(
    items: List[PolicyIn],
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("insurance:upload")),
):
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
def upload_cancellations_bulk(
    items: List[CancellationIn],
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("insurance:upload")),
):
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


@router.post("/fraud-flags/bulk")
def upload_fraud_flags_bulk(
    items: List[FraudFlagIn],
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("insurance:upload")),
):
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
    log(db, "INSURANCE_FRAUD_FLAGS_UPLOAD", actor=u, entity=None, target_ref=str(inserted), meta={"rows": inserted})
    return {"inserted": inserted}
