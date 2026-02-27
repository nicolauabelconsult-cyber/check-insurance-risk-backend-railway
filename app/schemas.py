# app/schemas.py
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, ConfigDict, AliasChoices
from typing import Any, Dict, List, Literal, Optional


# ---------------- AUTH ----------------
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


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class LoginOut(BaseModel):
    access_token: str
    refresh_token: str
    user: UserOut


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str


# ---------------- ENTITIES ----------------
class EntityCreate(BaseModel):
    name: str
    type: str  # "BANK" | "INSURER" | "OTHER"


class EntityUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None  # "ACTIVE" | "DISABLED"


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
    role: str
    entity_id: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    entity_id: Optional[str] = None


class ResetPasswordIn(BaseModel):
    new_password: str


# ---------------- SOURCES ----------------
class SourceCreate(BaseModel):
    # SUPER_ADMIN/ADMIN pode criar para qualquer entity_id
    # CLIENT_* cria só para a sua entidade
    entity_id: Optional[str] = None
    name: str
    category: str
    tags: Optional[list[str]] = None
    # canonical field is collected_from; accept legacy frontend key "origin" too
    collected_from: Optional[str] = Field(default=None, validation_alias=AliasChoices("collected_from", "origin"))


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    collected_from: Optional[str] = None
    status: Optional[str] = None


class SourceOut(BaseModel):
    id: str
    entity_id: str
    name: str
    category: str
    origin: Optional[str] = None
    tags: Optional[list[str]] = None
    collected_from: Optional[str] = None
    status: str


# ---------------- RISKS ----------------
class RiskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    entity_id: str

    name: str | None = Field(default=None, validation_alias="query_name")
    bi: str | None = Field(default=None, validation_alias="query_bi")
    passport: str | None = Field(default=None, validation_alias="query_passport")
    nationality: str | None = Field(default=None, validation_alias="query_nationality")

    score: str | None = None
    summary: str | None = None
    matches: list[Any] = []
    status: str


class RiskSearchIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    entity_id: str | None = None
    full_name: str = Field(..., alias="name")
    nationality: str | None = None


class CandidateOut(BaseModel):
    id: str
    full_name: str
    nationality: Optional[str] = None
    dob: Optional[str] = None
    doc_type: Optional[str] = None
    doc_last4: Optional[str] = None
    sources: List[str] = []
    match_score: int


class RiskSearchOut(BaseModel):
    disambiguation_required: bool
    candidates: List[CandidateOut]


class RiskConfirmIn(BaseModel):
    # ✅ clients: pode omitir -> backend usa u.entity_id
    # ✅ admins: pode enviar entity_id
    entity_id: Optional[str] = None

    # ID do candidato escolhido. Use "NO_MATCH" para relatório sem correspondência.
    candidate_id: str

    # Pesquisa base
    name: str
    nationality: Optional[str] = None

    # 🔐 Validação opcional (2º nível) para reduzir homónimos
    # Se não for fornecido, o sistema confirma apenas por nome.
    id_type: Optional[Literal["BI", "PASSPORT"]] = None
    id_number: Optional[str] = None


# ---------------- AUDIT ----------------
class AuditOut(BaseModel):
    id: str
    action: str
    actor_name: str
    entity_name: Optional[str] = None
    target_ref: Optional[str] = None
    meta: Dict[str, Any] = {}
    created_at: str
