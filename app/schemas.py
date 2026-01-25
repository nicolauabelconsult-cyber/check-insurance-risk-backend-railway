from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional

class EntityOut(BaseModel):
    id: str
    name: str
    type: Literal["BANK","INSURANCE","OTHER"]
    status: Literal["ACTIVE","INACTIVE"]

class EntityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    type: Literal["BANK","INSURANCE","OTHER"]

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
    name: str
    email: EmailStr
    password: str = Field(min_length=6)
    role: Literal["ADMIN","CLIENT_ADMIN","CLIENT_ANALYST"]
    entity_id: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class LoginOut(BaseModel):
    access_token: str
    refresh_token: str
    user: UserOut
