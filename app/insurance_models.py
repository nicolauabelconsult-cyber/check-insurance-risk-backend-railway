from __future__ import annotations

from sqlalchemy import Column, String, Integer, Boolean, Date, DateTime, Text
from sqlalchemy.sql import text

from app.db import Base


class InsurancePayment(Base):
    __tablename__ = "insurance_payments"

    id = Column(String, primary_key=True)
    entity_id = Column(String, nullable=False, index=True)

    bi = Column(String, nullable=True, index=True)
    passport = Column(String, nullable=True, index=True)
    full_name = Column(String, nullable=True, index=True)

    due_date = Column(Date, nullable=True)
    paid_date = Column(Date, nullable=True)
    amount = Column(Integer, nullable=True)
    is_paid = Column(Boolean, nullable=False, server_default=text("false"))

    created_at = Column(DateTime, nullable=False, server_default=text("now()"))


class InsuranceClaim(Base):
    __tablename__ = "insurance_claims"

    id = Column(String, primary_key=True)
    entity_id = Column(String, nullable=False, index=True)

    bi = Column(String, nullable=True, index=True)
    passport = Column(String, nullable=True, index=True)
    full_name = Column(String, nullable=True, index=True)

    claim_date = Column(Date, nullable=True)
    claim_type = Column(String, nullable=True)
    amount_paid = Column(Integer, nullable=True)
    amount_reserved = Column(Integer, nullable=True)
    status = Column(String, nullable=True)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=text("now()"))


class InsurancePolicy(Base):
    __tablename__ = "insurance_policies"

    id = Column(String, primary_key=True)
    entity_id = Column(String, nullable=False, index=True)

    bi = Column(String, nullable=True, index=True)
    passport = Column(String, nullable=True, index=True)
    full_name = Column(String, nullable=True, index=True)

    policy_no = Column(String, nullable=False, index=True)
    product_type = Column(String, nullable=True)
    status = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    premium = Column(Integer, nullable=True)
    sum_insured = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=text("now()"))


class InsuranceCancellation(Base):
    __tablename__ = "insurance_cancellations"

    id = Column(String, primary_key=True)
    entity_id = Column(String, nullable=False, index=True)

    bi = Column(String, nullable=True, index=True)
    passport = Column(String, nullable=True, index=True)
    full_name = Column(String, nullable=True, index=True)

    policy_no = Column(String, nullable=True, index=True)
    date = Column(Date, nullable=True)
    reason = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=text("now()"))


class InsuranceFraudFlag(Base):
    __tablename__ = "insurance_fraud_flags"

    id = Column(String, primary_key=True)
    entity_id = Column(String, nullable=False, index=True)

    bi = Column(String, nullable=True, index=True)
    passport = Column(String, nullable=True, index=True)
    full_name = Column(String, nullable=True, index=True)

    flag = Column(String, nullable=False)
    severity = Column(String, nullable=True)  # LOW|MEDIUM|HIGH
    note = Column(Text, nullable=True)
    date = Column(Date, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=text("now()"))
