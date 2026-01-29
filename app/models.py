import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from .db import Base

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
    collected_from = Column(String, nullable=False)  # onde foi recolhida
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
