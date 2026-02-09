from __future__ import annotations

from pydantic import BaseModel, EmailStr
from typing import Optional, Any, List, Literal, Dict


# ---------------- USERS / AUTH ----------------

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
    type: str


class EntityUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None


class EntityOut(BaseModel):
    id: str
    name: str
    type: str
    status: str


# ---------------- USERS (CRUD) ----------------

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str
    entity_id: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    entity_id: Optional[str] = None


class ResetPasswordIn(BaseModel):
    new_password: str


# ---------------- SOURCES ----------------

class SourceCreate(BaseModel):
    entity_id: Optional[str] = None
    name: str
    category: str
    collected_from: str


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
    collected_from: str
    status: str


# ---------------- RISKS (LIST/DETAIL/CREATE) ----------------

class RiskCreate(BaseModel):
    entity_id: Optional[str] = None
    name: Optional[str] = None
    bi: Optional[str] = None
    passport: Optional[str] = None
    nationality: Optional[str] = None
    selected_candidate_id: Optional[str] = None


class RiskOut(BaseModel):
    id: str
    entity_id: str
    name: Optional[str] = None
    bi: Optional[str] = None
    passport: Optional[str] = None
    nationality: Optional[str] = None
    score: Optional[str] = None
    summary: Optional[str] = None
    matches: List[Any] = []
    status: str


# ---------------- SEARCH / CONFIRM (OPÇÃO A) ----------------

class RiskSearchIn(BaseModel):
    entity_id: str
    name: str
    nationality: Optional[str] = None


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
    entity_id: str
    candidate_id: str
    name: str
    nationality: str
    id_type: Literal["BI", "PASSPORT"]
    id_number: str


# ---------------- AUDIT ----------------

class AuditOut(BaseModel):
    id: str
    action: str
    actor_name: str
    entity_name: Optional[str] = None
    target_ref: Optional[str] = None
    meta: Dict[str, Any] = {}
    created_at: str
