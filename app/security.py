import time
from typing import Any, Dict, Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
from .settings import settings

pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(p: str) -> str:
    return pwd.hash(p)

def verify_password(p: str, hashed: str) -> bool:
    return pwd.verify(p, hashed)

def create_token(
    sub: str,
    token_type: str,                 # "access" | "refresh"
    role: str,
    entity_id: Optional[str] = None,
    minutes: Optional[int] = None,
    days: Optional[int] = None,
) -> str:
    now = int(time.time())

    if token_type == "access":
        exp = now + int(minutes or settings.JWT_ACCESS_MINUTES) * 60
    else:
        exp = now + int(days or settings.JWT_REFRESH_DAYS) * 24 * 60 * 60

    payload: Dict[str, Any] = {
        "sub": sub,
        "type": token_type,
        "role": role,
        "entity_id": entity_id,
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        raise
