from datetime import datetime
from enum import Enum
from typing import Optional  # 👈 ADICIONA ISTO (podes pôr também List se quiseres)

from sqlalchemy import (
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskDecision(str, Enum):
    APPROVED = "APROVADO"
    REJECTED = "REJEITADO"
    UNDER_INVESTIGATION = "SOB_INVESTIGACAO"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=UserRole.ANALYST.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    risk_records = relationship("RiskRecord", back_populates="analyst")

class InfoSource(Base):
    __tablename__ = "info_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    records_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_by = relationship("User")
    entities = relationship("NormalizedEntity", back_populates="source")


class NormalizedEntity(Base):
    __tablename__ = "normalized_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("info_sources.id"))
    source_type: Mapped[str] = mapped_column(String(50))
    source_risk_weight: Mapped[int] = mapped_column(Integer, default=0)

    full_name_norm: Mapped[str] = mapped_column(Text, index=True)
    nif_norm: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    passport_norm: Mapped[Optional[str]] = mapped_column(
        String(100), index=True, nullable=True
    )
    resident_card_norm: Mapped[Optional[str]] = mapped_column(
        String(100), index=True, nullable=True
    )

    country_code: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    role_or_position: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    source = relationship("InfoSource", backref="entities")


class RiskRecord(Base):
    __tablename__ = "risk_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # dados de entrada
    full_name: Mapped[str] = mapped_column(Text)
    full_name_norm: Mapped[str] = mapped_column(Text, index=True)
    nif: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    passport: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    resident_card: Mapped[Optional[str]] = mapped_column(
        String(100), index=True, nullable=True
    )
    country_code: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)

    # resultado
    score: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(20))  # LOW/MEDIUM/HIGH/CRITICAL
    decision: Mapped[Optional[str]] = mapped_column(
        String(30), default="PENDING"
    )  # APROVADO, REJEITADO, SOB_INVESTIGACAO

    explanation: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # lista de fatores
    sources_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    relations_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    analyst_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    analyst = relationship("User")


class RiskMatch(Base):
    __tablename__ = "risk_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    risk_record_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("risk_records.id"), index=True
    )
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("normalized_entities.id"), index=True
    )

    match_score: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    risk_record = relationship("RiskRecord", backref="matches")
    entity = relationship("NormalizedEntity")
    
class UserRole(str, Enum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskDecision(str, Enum):
    APPROVED = "APROVADO"
    REJECTED = "REJEITADO"
    UNDER_INVESTIGATION = "SOB_INVESTIGACAO"
