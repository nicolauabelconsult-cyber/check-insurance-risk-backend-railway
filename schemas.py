from pydantic import BaseModel, EmailStr
from typing import Optional

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserRead(BaseModel):
    id: int
    username: str
    name: Optional[str] = None
    email: Optional[str] = None
    role: str
    is_active: bool

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "ANALYST"
    name: Optional[str] = None
    email: Optional[EmailStr] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None

class ResetPasswordIn(BaseModel):
    password: str

class InfoSourceRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    row_count: Optional[int] = None

    class Config:
        from_attributes = True
