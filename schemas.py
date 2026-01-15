from pydantic import BaseModel
from typing import Optional

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserRead(BaseModel):
    id: int
    username: str
    role: str
    entity_id: Optional[int]
    is_active: bool
    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    entity_id: Optional[int]

class EntityCreate(BaseModel):
    name: str

class AnalysisCreate(BaseModel):
    subject_name: str

class AnalysisRead(BaseModel):
    id: int
    subject_name: str
    risk_score: int
    risk_level: str
