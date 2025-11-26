from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


# -------------------------
# MODELOS DE AUTENTICAÇÃO
# -------------------------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# -------------------------
# MODELOS DE UTILIZADOR
# -------------------------

class UserRead(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    # Permite criar o schema directamente a partir do modelo SQLAlchemy
    model_config = ConfigDict(from_attributes=True)
