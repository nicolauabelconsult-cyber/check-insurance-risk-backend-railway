from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, JSON, Text, Integer
from sqlalchemy.orm import relationship

from .db import Base

# Se estiveres em Postgres, JSONB é melhor para campos underwriting.
try:
    from sqlalchemy.dialects.postgresql import JSONB
except Exception:
    JSONB = JSON  # fallback


class EntityType(str, enum.Enum):
    INSURER = "INSURER"
    BANK = "BANK"
    OTHER = "OTHER"


class EntityStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    CLIENT_ADMIN = "CLIENT_ADMIN"
    CLIENT_ANALYST = "CLIENT_ANALYST"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class SourceStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class RiskStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    DONE = "DONE"


class Entity(Base):
    __tablename__ = "entities"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    type = Column(Enum(EntityType), nullable=False)
    status = Column(Enum(EntityStatus), nullable=False, default=EntityStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="entity")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)

    role = Column(Enum(UserRole), nullable=False)
    status = Column(Enum(UserStatus), nullable=False, default=UserStatus.ACTIVE)

    entity_id = Column(String, ForeignKey("entities.id"), nullable=True)
    entity = relationship("Entity", back_populates="users")

    created_at = Column(DateTime, default=datetime.utcnow)


class Source(Base):
    __tablename__ = "sources"

    id = Column(String, primary_key=True)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=False, index=True)

    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    collected_from = Column(String, nullable=False)  # origem

    status = Column(Enum(SourceStatus), nullable=False, default=SourceStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)


class Risk(Base):
    __tablename__ = "risks"

    id = Column(String, primary_key=True)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=False, index=True)

    # pesquisa por:
    query_name = Column(String, nullable=True)
    query_bi = Column(String, nullable=True)
    query_passport = Column(String, nullable=True)
    query_nationality = Column(String, nullable=True)

    # resultado (mock por agora / pronto para integrar o motor real)
    score = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    matches = Column(JSON, nullable=False, default=list)  # lista de matches

    status = Column(Enum(RiskStatus), nullable=False, default=RiskStatus.DRAFT)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Underwriting (campos preparados)
    uw_score = Column(Integer, nullable=True)
    uw_decision = Column(String, nullable=True)
    uw_summary = Column(Text, nullable=True)
    uw_kpis = Column(JSONB, nullable=True)
    uw_factors = Column(JSONB, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True)
    action = Column(String, nullable=False)

    actor_id = Column(String, nullable=True)
    actor_name = Column(String, nullable=False, default="Unknown")

    entity_id = Column(String, nullable=True)
    entity_name = Column(String, nullable=True)

    target_ref = Column(String, nullable=True)
    meta = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)

class InsurancePolicy(Base):
    __tablename__ = "insurance_policies"

    id = Column(String, primary_key=True)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=False, index=True)

    subject_full_name = Column(String, nullable=True, index=True)
    subject_bi = Column(String, nullable=True, index=True)
    subject_passport = Column(String, nullable=True, index=True)

    product_type = Column(String, nullable=False, index=True)

    policy_number = Column(String, nullable=True, index=True)
    insurer_name = Column(String, nullable=True)
    status = Column(String, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)

    currency = Column(String, nullable=True)
    premium_amount = Column(Integer, nullable=True)
    sum_insured = Column(Integer, nullable=True)

    source_name = Column(String, nullable=True)
    source_ref = Column(String, nullable=True)
    raw_payload = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=False, index=True)

    subject_full_name = Column(String, nullable=True, index=True)
    subject_bi = Column(String, nullable=True, index=True)
    subject_passport = Column(String, nullable=True, index=True)

    product_type = Column(String, nullable=False, index=True)
    policy_number = Column(String, nullable=True, index=True)

    amount = Column(Integer, nullable=True)
    currency = Column(String, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    due_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=True)

    source_name = Column(String, nullable=True)
    source_ref = Column(String, nullable=True)
    raw_payload = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class Claim(Base):
    __tablename__ = "claims"

    id = Column(String, primary_key=True)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=False, index=True)

    subject_full_name = Column(String, nullable=True, index=True)
    subject_bi = Column(String, nullable=True, index=True)
    subject_passport = Column(String, nullable=True, index=True)

    product_type = Column(String, nullable=False, index=True)
    policy_number = Column(String, nullable=True, index=True)

    claim_number = Column(String, nullable=True, index=True)
    loss_date = Column(DateTime, nullable=True)
    reported_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=True)
    amount_claimed = Column(Integer, nullable=True)
    amount_paid = Column(Integer, nullable=True)
    currency = Column(String, nullable=True)

    source_name = Column(String, nullable=True)
    source_ref = Column(String, nullable=True)
    raw_payload = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class Cancellation(Base):
    __tablename__ = "cancellations"

    id = Column(String, primary_key=True)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=False, index=True)

    subject_full_name = Column(String, nullable=True, index=True)
    subject_bi = Column(String, nullable=True, index=True)
    subject_passport = Column(String, nullable=True, index=True)

    product_type = Column(String, nullable=False, index=True)
    policy_number = Column(String, nullable=True, index=True)

    cancelled_at = Column(DateTime, nullable=True)
    reason = Column(String, nullable=True)

    source_name = Column(String, nullable=True)
    source_ref = Column(String, nullable=True)
    raw_payload = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class FraudFlag(Base):
    __tablename__ = "fraud_flags"

    id = Column(String, primary_key=True)
    entity_id = Column(String, ForeignKey("entities.id"), nullable=False, index=True)

    subject_full_name = Column(String, nullable=True, index=True)
    subject_bi = Column(String, nullable=True, index=True)
    subject_passport = Column(String, nullable=True, index=True)

    product_type = Column(String, nullable=False, index=True)
    policy_number = Column(String, nullable=True, index=True)

    flag_type = Column(String, nullable=False)
    severity = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    source_name = Column(String, nullable=True)
    source_ref = Column(String, nullable=True)
    raw_payload = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
