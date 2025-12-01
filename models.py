from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column,
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


# =========================================================
# ENUMS
# =========================================================

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


# =========================================================
# USER
# =========================================================
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))

    role: Mapped[str] = mapped_column(String(20), default=UserRole.ANALYST.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relacionamento com registos de risco
    risk_records = relationship("RiskRecord", back_populates="analyst")


# =========================================================
# INFO SOURCE
# =========================================================
class InfoSource(Base):
    __tablename__ = "info_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_type = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relacionamento com entidades normalizadas
    entities = relationship(
        "NormalizedEntity",
        back_populates="source",
        cascade="all, delete-orphan",
    )


# =========================================================
# NORMALIZED ENTITY  (entidades para multi-match)
# =========================================================
class NormalizedEntity(Base):
    __tablename__ = "normalized_entities"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(255), nullable=True)
    normalized_name = Column(String(255), index=True, nullable=True)

    nif = Column(String(100), index=True, nullable=True)
    passport = Column(String(100), index=True, nullable=True)
    resident_card = Column(String(100), index=True, nullable=True)

    country = Column(String(3), nullable=True)

    info_source_id = Column(Integer, ForeignKey("info_sources.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("InfoSource", back_populates="entities")


# =========================================================
# RISK RECORD
# =========================================================
class RiskRecord(Base):
    __tablename__ = "risk_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Identificadores
    full_name: Mapped[str] = mapped_column(String(255))
    nif: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    passport: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resident_card: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)

    # Resultado da análise
    score: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(20))  # RiskLevel.value
    decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    decision_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    explanation: Mapped[Optional[JSON]] = mapped_column(JSON, nullable=True)

    # Ligações
    confirmed_entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("normalized_entities.id"),
        nullable=True,
    )
    analyst_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    analyst = relationship("User", back_populates="risk_records")
    confirmed_entity = relationship("NormalizedEntity")

    # Alertas associados
    alerts = relationship("RiskAlert", back_populates="risk_record")

    # Matches associados
    matches = relationship("RiskMatch", back_populates="risk_record")


# =========================================================
# RISK MATCH — guarda cada match de cada registo
# =========================================================
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

    risk_record = relationship("RiskRecord", back_populates="matches")
    entity = relationship("NormalizedEntity")


# =========================================================
# RISK ALERT — alertas como PEP, sanções, fraude etc.
# =========================================================
class RiskAlert(Base):
    __tablename__ = "risk_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    risk_record_id: Mapped[int] = mapped_column(
        ForeignKey("risk_records.id"), nullable=False
    )

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    risk_record = relationship("RiskRecord", back_populates="alerts")
