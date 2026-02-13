from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Date,
    DateTime,
    Boolean,
    Text,
    Index,
)
from app.db import Base


class InsurancePayment(Base):
    __tablename__ = "insurance_payments"

    id = Column(String, primary_key=True)
    entity_id = Column(String, index=True, nullable=False)

    bi = Column(String, index=True, nullable=True)
    passport = Column(String, index=True, nullable=True)
    full_name = Column(String, index=True, nullable=True)

    due_date = Column(Date, nullable=True)
    paid_date = Column(Date, nullable=True)
    amount = Column(Integer, nullable=True)  # AOA
    is_paid = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class InsuranceClaim(Base):
    __tablename__ = "insurance_claims"

    id = Column(String, primary_key=True)
    entity_id = Column(String, index=True, nullable=False)

    bi = Column(String, index=True, nullable=True)
    passport = Column(String, index=True, nullable=True)
    full_name = Column(String, index=True, nullable=True)

    claim_date = Column(Date, nullable=True)
    claim_type = Column(String, nullable=True)       # AUTO/VIDA/PATRIMONIAL/etc
    amount_paid = Column(Integer, nullable=True)     # AOA
    amount_reserved = Column(Integer, nullable=True) # AOA
    status = Column(String, nullable=True)           # ABERTO/FECHADO/REJEITADO
    note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class InsurancePolicy(Base):
    __tablename__ = "insurance_policies"

    id = Column(String, primary_key=True)
    entity_id = Column(String, index=True, nullable=False)

    bi = Column(String, index=True, nullable=True)
    passport = Column(String, index=True, nullable=True)
    full_name = Column(String, index=True, nullable=True)

    policy_no = Column(String, index=True, nullable=False)
    product_type = Column(String, nullable=True)   # AUTO/VIDA/etc
    status = Column(String, nullable=True)         # ATIVA/CANCELADA/EXPIRADA
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    premium = Column(Integer, nullable=True)       # AOA
    sum_insured = Column(Integer, nullable=True)   # AOA

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class InsuranceCancellation(Base):
    __tablename__ = "insurance_cancellations"

    id = Column(String, primary_key=True)
    entity_id = Column(String, index=True, nullable=False)

    bi = Column(String, index=True, nullable=True)
    passport = Column(String, index=True, nullable=True)
    full_name = Column(String, index=True, nullable=True)

    policy_no = Column(String, index=True, nullable=True)
    date = Column(Date, nullable=True)
    reason = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class InsuranceFraudFlag(Base):
    __tablename__ = "insurance_fraud_flags"

    id = Column(String, primary_key=True)
    entity_id = Column(String, index=True, nullable=False)

    bi = Column(String, index=True, nullable=True)
    passport = Column(String, index=True, nullable=True)
    full_name = Column(String, index=True, nullable=True)

    flag = Column(String, nullable=False)
    severity = Column(String, nullable=True)  # BAIXO/MÉDIO/ALTO
    note = Column(Text, nullable=True)
    date = Column(Date, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# Índices compostos (performance e multi-tenant)
Index("ix_payments_entity_bi_pass", InsurancePayment.entity_id, InsurancePayment.bi, InsurancePayment.passport)
Index("ix_claims_entity_bi_pass", InsuranceClaim.entity_id, InsuranceClaim.bi, InsuranceClaim.passport)
Index("ix_policies_entity_bi_pass", InsurancePolicy.entity_id, InsurancePolicy.bi, InsurancePolicy.passport)
Index("ix_cancel_entity_bi_pass", InsuranceCancellation.entity_id, InsuranceCancellation.bi, InsuranceCancellation.passport)
Index("ix_fraud_entity_bi_pass", InsuranceFraudFlag.entity_id, InsuranceFraudFlag.bi, InsuranceFraudFlag.passport)
