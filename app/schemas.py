# app/schemas.py
from __future__ import annotations

from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Any, Dict, List, Literal, Optional


# ---------------- AUTH ----------------
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


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

    # auth.py envia isto (role_perms)
    permissions: Optional[List[str]] = None


class LoginOut(BaseModel):
    access_token: str
    refresh_token: str
    user: UserOut


# ---------------- ENTITIES ----------------
class EntityCreate(BaseModel):
    name: str
    # conforme models.EntityType
    type: Literal["INSURANCE", "BANK", "OTHER"] = "OTHER"


class EntityUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[Literal["INSURANCE", "BANK", "OTHER"]] = None
    status: Optional[Literal["ACTIVE", "DISABLED"]] = None


class EntityOut(BaseModel):
    id: str
    name: str
    type: str
    status: str


# ---------------- USERS ----------------
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    # conforme models.UserRole
    role: Literal["SUPER_ADMIN", "ADMIN", "CLIENT_ADMIN", "CLIENT_ANALYST"] = "CLIENT_ANALYST"
    status: Literal["ACTIVE", "DISABLED"] = "ACTIVE"
    entity_id: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[Literal["SUPER_ADMIN", "ADMIN", "CLIENT_ADMIN", "CLIENT_ANALYST"]] = None
    status: Optional[Literal["ACTIVE", "DISABLED"]] = None
    entity_id: Optional[str] = None
    password: Optional[str] = None


class ResetPasswordIn(BaseModel):
    new_password: str


# ---------------- SOURCES ----------------
class SourceCreate(BaseModel):
    # SUPER_ADMIN pode criar para qualquer entidade
    entity_id: Optional[str] = None
    name: str
    category: str
    collected_from: Optional[str] = None


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    collected_from: Optional[str] = None
    status: Optional[Literal["ACTIVE", "DISABLED"]] = None


class SourceOut(BaseModel):
    id: str
    entity_id: str
    name: str
    category: str
    collected_from: Optional[str] = None
    status: str


# ---------------- RISKS ----------------
class RiskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_id: str
    created_by: str
    status: str

    query_name: Optional[str] = None
    query_bi: Optional[str] = None
    query_passport: Optional[str] = None
    query_nationality: Optional[str] = None

    score: Optional[str] = None
    summary: Optional[str] = None
    matches: Any = None
    created_at: Optional[Any] = None


# Alinhado ao frontend RiskCreate.tsx
class RiskSearchIn(BaseModel):
    # só ADMIN envia; clientes não enviam
    entity_id: Optional[str] = None

    # frontend envia "name" e "nationality"
    name: str
    nationality: Optional[str] = None


class CandidateOut(BaseModel):
    # frontend usa: id, full_name, nationality, doc_type, doc_last4, match_score, sources
    id: str
    full_name: str
    nationality: Optional[str] = None
    doc_type: Optional[str] = None
    doc_last4: Optional[str] = None
    sources: List[str] = []
    match_score: int


class RiskSearchOut(BaseModel):
    candidates: List[CandidateOut] = []
    disambiguation_required: bool = False
    risk: Optional[RiskOut] = None


class RiskConfirmIn(BaseModel):
    # só ADMIN envia; clientes não enviam
    entity_id: Optional[str] = None

    candidate_id: str
    name: str
    nationality: str
    id_type: Literal["BI", "PASSPORT"]
    id_number: str


# ---------------- AUDIT ----------------
class AuditOut(BaseModel):
    id: str
    entity_id: Optional[str] = None
    actor_id: str
    action: str
    target_ref: Optional[str] = None
    meta: Dict[str, Any] = {}
    created_at: Any
