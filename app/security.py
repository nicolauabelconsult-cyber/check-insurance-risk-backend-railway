import time
from typing import Any, Dict, Optional

import jwt
from passlib.context import CryptContext
from .settings import settings

pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(p: str) -> str:
    return pwd.hash(p)

def verify_password(p: str, hashed: str) -> bool:
    return pwd.verify(p, hashed)

def create_token(
    sub: str,
    token_type: str,          # "access" | "refresh"
    role: str,
    entity_id: Optional[str] = None,
    expires_minutes: int = 60 * 6,
    refresh_days: int = 15,
) -> str:
    now = int(time.time())

    if token_type == "access":
        exp = now + int(expires_minutes) * 60
    elif token_type == "refresh":
        exp = now + int(refresh_days) * 24 * 60 * 60
    else:
        raise ValueError("Invalid token_type")

    payload: Dict[str, Any] = {
        "sub": sub,
        "type": token_type,     # ✅ o deps.py espera isto
        "role": role,
        "entity_id": entity_id,
        "iat": now,
        "exp": exp,
    }

    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
