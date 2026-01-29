import time
from typing import Any, Dict, Optional

import jwt
from passlib.context import CryptContext

from .settings import settings

# Password hashing (sem bcrypt, para não dar conflito no Render)
pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(p: str) -> str:
    return pwd.hash(p)


def verify_password(p: str, hashed: str) -> bool:
    return pwd.verify(p, hashed)


def create_token(
    sub: str,
    role: str,
    entity_id: Optional[str] = None,
    expires_minutes: int = 60 * 24,  # 24h default
) -> str:
    """
    Cria JWT com:
      - sub: user_id (ou email, mas recomendo user_id)
      - role
      - entity_id
      - exp
      - iat
    """
    now = int(time.time())
    payload: Dict[str, Any] = {
        "sub": sub,
        "role": role,
        "entity_id": entity_id,
        "iat": now,
        "exp": now + int(expires_minutes) * 60,
    }

    # settings.JWT_SECRET deve existir
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    return token


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodifica e valida o JWT.
    Lança exceção se inválido/expirado.
    """
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
