# app/schemas.py
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, ConfigDict
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


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshIn(BaseModel):
    refresh_token: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


# ---------------- ENTITIES ----------------
class EntityCreate(BaseModel):
    name: str
    type: Literal["BANKING", "INSURANCE", "PENSION", "BROKER", "OTHER"] = "OTHER"
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"


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
    role: Literal["SUPER_ADMIN", "ADMIN", "CLIENT"] = "CLIENT"
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"
    entity_id: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[Literal["SUPER_ADMIN", "ADMIN", "CLIENT"]] = None
    status: Optional[Literal["ACTIVE", "INACTIVE"]] = None
    entity_id: Optional[str] = None
    password: Optional[str] = None


class UserListOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    status: str
    entity_id: Optional[str] = None


# ---------------- SOURCES ----------------
class SourceCreate(BaseModel):
    name: str
    category: Literal["PEP", "SANCTIONS", "INSURANCE"] = "PEP"
    jurisdiction: str = "ANGOLA"
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"
    notes: Optional[str] = None


class SourceOut(BaseModel):
    id: str
    entity_id: str
    name: str
    category: str
    jurisdiction: str
    status: str
    notes: Optional[str] = None


# ---------------- RISKS ----------------
class RiskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_id: str
    created_by: str
    status: str
    query_name: Optional[str] = None
    query_nationality: Optional[str] = None
    score: Optional[int] = None
    matches: Any = None
    created_at: Optional[Any] = None


class RiskSearchIn(BaseModel):
    # ✅ clients: pode omitir -> backend usa u.entity_id
    # ✅ admins: pode enviar entity_id
    entity_id: Optional[str] = None

    full_name: str
    nationality: str
    id_type: Literal["BI", "PASSPORT"]
    id_number: str


class CandidateOut(BaseModel):
    # placeholder para futuro motor real
    id: str
    full_name: str
    nationality: Optional[str] = None
    doc_last4: Optional[str] = None
    sources: List[str] = []
    match_score: int


class RiskSearchOut(BaseModel):
    # frontend usa isto: out.candidates
    candidates: List[CandidateOut] = []

    # quando o motor exigir escolha (futuro)
    disambiguation_required: bool = False

    # Risk criado em DRAFT para persistência / rastreio
    risk: Optional[RiskOut] = None


class RiskConfirmIn(BaseModel):
    # ✅ clients: pode omitir -> backend usa u.entity_id
    # ✅ admins: pode enviar entity_id
    entity_id: Optional[str] = None
    candidate_id: str
    name: str
    nationality: str
    id_type: Literal["BI", "PASSPORT"]
    id_number: str


# ---------------- AUDIT ----------------
class AuditOut(BaseModel):
    id: str
    entity_id: str
    actor_id: str
    action: str
    object_type: str
    object_id: str
    payload: Dict[str, Any] = {}
    created_at: Any


# ---------------- DASHBOARD ----------------
class DashboardSummaryOut(BaseModel):
    entities: int
    users: int
    sources: int
    risks_total: int
    risks_draft: int
    risks_confirmed: int
    avg_score: float
