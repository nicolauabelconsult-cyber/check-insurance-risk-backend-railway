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

def create_token(sub: str, token_type: str, minutes: int | None = None, days: int | None = None) -> str:
    now = int(time.time())
    exp = now + 3600  # default 1h

    if minutes is not None:
        exp = now + int(minutes) * 60
    if days is not None:
        exp = now + int(days) * 24 * 60 * 60

    payload: Dict[str, Any] = {
        "sub": sub,
        "type": token_type,   # ✅ muito importante
        "iat": now,
        "exp": exp,
    }

    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
