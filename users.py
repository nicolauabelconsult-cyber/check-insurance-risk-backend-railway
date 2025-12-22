from pydantic import BaseModel, EmailStr
from typing import Optional

class UserRead(BaseModel):
    id: int
    username: str
    name: Optional[str] = None
    email: Optional[str] = None
    role: str
    is_active: bool = True

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
