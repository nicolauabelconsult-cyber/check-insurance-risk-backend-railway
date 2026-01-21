from typing import Optional, Literal
from pydantic import BaseModel

Role = Literal["SUPER_ADMIN","PLATFORM_ADMIN","CLIENT_ADMIN","CLIENT_ANALYST"]

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class EntityCreate(BaseModel):
    name: str

class EntityRead(BaseModel):
    id: int
    name: str
    class Config: from_attributes = True

class UserCreate(BaseModel):
    username: str
    password: str
    role: Role
    entity_id: Optional[int] = None

class UserUpdate(BaseModel):
    role: Optional[Role] = None
    entity_id: Optional[int] = None
    is_active: Optional[bool] = None

class UserRead(BaseModel):
    id: int
    username: str
    role: str
    entity_id: Optional[int]
    is_active: bool
    class Config: from_attributes = True

class ResetPasswordIn(BaseModel):
    password: str

class AnalysisCreate(BaseModel):
    subject_name: str

class AnalysisRead(BaseModel):
    id: int
    reference: str
    subject_name: str
    risk_score: int
    risk_level: str
    pep: bool
    pep_reason: Optional[str]
    class Config: from_attributes = True

class InfoSourceRead(BaseModel):
    id: int
    name: str
    class Config: from_attributes = True

class AuditLogRead(BaseModel):
    id: int
    action: str
    detail: Optional[str]
    created_at: str
    class Config: from_attributes = True
