# app/schemas.py
from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


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


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    role: str = Field(..., description="SUPER_ADMIN | ADMIN | CLIENT_ADMIN | CLIENT_ANALYST")
    status: Optional[str] = "ACTIVE"
    entity_id: Optional[str] = None

    # ✅ SUPER_ADMIN pode definir password
    # ✅ Se vier vazio, backend gera temp_password
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
