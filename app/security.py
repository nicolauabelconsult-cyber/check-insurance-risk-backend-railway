import time
from typing import Any, Dict, Optional

from jose import jwt
from passlib.context import CryptContext

from .settings import settings

# hashing sem bcrypt para evitar conflitos no Render
pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(p: str) -> str:
    return pwd.hash(p)


def verify_password(p: str, hashed: str) -> bool:
    return pwd.verify(p, hashed)


def create_token(
    sub: str,
    token_type: str,  # "access" | "refresh"
    role: Optional[str] = None,
    entity_id: Optional[str] = None,
    minutes: Optional[int] = None,
    days: Optional[int] = None,
) -> str:
    now = int(time.time())
    exp = now + 60 * 60  # default 1h

    if minutes is not None:
        exp = now + int(minutes) * 60
    if days is not None:
        exp = now + int(days) * 24 * 60 * 60

    payload: Dict[str, Any] = {
        "sub": sub,
        "type": token_type,
        "iat": now,
        "exp": exp,
    }
    if role is not None:
        payload["role"] = role
    if entity_id is not None:
        payload["entity_id"] = entity_id

    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
