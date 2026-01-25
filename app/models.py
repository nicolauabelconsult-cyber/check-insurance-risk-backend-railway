import enum
from datetime import datetime
from sqlalchemy import String, DateTime, Enum, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class EntityType(str, enum.Enum):
    BANK = "BANK"
    INSURANCE = "INSURANCE"
    OTHER = "OTHER"

class EntityStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    CLIENT_ADMIN = "CLIENT_ADMIN"
    CLIENT_ANALYST = "CLIENT_ANALYST"

class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    type: Mapped[EntityType] = mapped_column(Enum(EntityType))
    status: Mapped[EntityStatus] = mapped_column(Enum(EntityStatus), default=EntityStatus.ACTIVE)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="entity")

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(500))

    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.ACTIVE)

    entity_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("entities.id"), nullable=True)
    entity: Mapped[Entity | None] = relationship(back_populates="users")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(200))
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    entity_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
