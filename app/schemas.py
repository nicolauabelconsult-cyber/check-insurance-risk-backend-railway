# app/schemas.py
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# ---------- AUTH ----------
class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4, max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str


class LoginOut(BaseModel):
    user: "UserOut"
    tokens: TokenOut


# ---------- ENTITIES ----------
class EntityOut(BaseModel):
    id: str
    name: str


# ---------- USERS ----------
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


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=4, max_length=128)
    role: str
    entity_id: str


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    role: Optional[str] = None
    status: Optional[str] = None


class ResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=4, max_length=128)


# ---------- SOURCES ----------
class SourceCreate(BaseModel):
    entity_id: str
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=80)
    collected_from: str = Field(min_length=2, max_length=120)


class SourceOut(BaseModel):
    id: str
    entity_id: str
    name: str
    category: str
    collected_from: str
    status: str


# ---------- RISKS ----------
class RiskOut(BaseModel):
    id: str
    entity_id: str
    score: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None


# resolve forward refs
LoginOut.model_rebuild()
