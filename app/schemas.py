from pydantic import BaseModel, EmailStr
from typing import Optional, Any, List, Literal

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
    permissions: List[str] = []   # ✅ fica aqui, uma única vez

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class LoginOut(BaseModel):
    access_token: str
    refresh_token: str
    user: UserOut

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
    matches: list[Any] = []
    status: str

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
