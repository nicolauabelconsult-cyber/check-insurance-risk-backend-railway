from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from database import Base

class Entity(Base):
    __tablename__ = "entities"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    hashed_password = Column(String)
    role = Column(String)  # SUPER_ADMIN | PLATFORM_ADMIN | CLIENT_ADMIN | CLIENT_ANALYST
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=True)
    is_active = Column(Boolean, default=True)

class InfoSource(Base):
    __tablename__ = "info_sources"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    file_path = Column(String)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(Integer, primary_key=True)
    reference = Column(String, unique=True)
    subject_name = Column(String)
    risk_score = Column(Integer)
    risk_level = Column(String)
    pep = Column(Boolean, default=False)
    pep_reason = Column(Text, nullable=True)
    entity_id = Column(Integer, ForeignKey("entities.id"))
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=True)
    action = Column(String)
    object_type = Column(String, nullable=True)
    object_id = Column(String, nullable=True)
    ip = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
