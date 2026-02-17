# app/schemas.py
from __future__ import annotations

from typing import Optional, Any, Dict, List
from pydantic import BaseModel, EmailStr, Field


# =========================
# AUTH
# =========================

class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str


class UserEntity(BaseModel):
    id: str
    name: str


class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    status: str
    entity: Optional[UserEntity] = None
    permissions: List[str] = []


class LoginOut(BaseModel):
    access_token: str
    refresh_token: str
    user: UserOut


# =========================
# ENTITIES
# =========================

class EntityIn(BaseModel):
    name: str
    type: str = Field(..., description="INSURER | BANK | OTHER")
    status: Optional[str] = "ACTIVE"


class EntityOut(BaseModel):
    id: str
    name: str
    type: str
    status: str


# =========================
# USERS
# =========================

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    role: str = Field(..., description="SUPER_ADMIN | ADMIN | CLIENT_ADMIN | CLIENT_ANALYST")
    status: Optional[str] = "ACTIVE"
    entity_id: Optional[str] = None

    # ✅ Opção 1: se não vier password, o backend gera uma temporária e devolve
    password: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    status: Optional[str] = None
    entity_id: Optional[str] = None


class UserCreateOut(BaseModel):
    user: UserOut
    temp_password: Optional[str] = None


# =========================
# SOURCES
# =========================

class SourceIn(BaseModel):
    entity_id: str
    name: str
    category: str
    collected_from: str


class SourceOut(BaseModel):
    id: str
    entity_id: str
    name: str
    category: str
    collected_from: str
    status: str


# =========================
# RISKS (mínimo para manter compatibilidade)
# =========================

class RiskCreate(BaseModel):
    entity_id: str
    query_name: Optional[str] = None
    query_bi: Optional[str] = None
    query_passport: Optional[str] = None
    query_nationality: Optional[str] = None


class RiskOut(BaseModel):
    id: str
    entity_id: str
    score: Optional[str] = None
    summary: Optional[str] = None
    status: str
    created_at: Optional[str] = None
