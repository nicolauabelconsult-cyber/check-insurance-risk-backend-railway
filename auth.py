"""
Módulo de autenticação – versão simples (sem Rust)
Usa passlib com sha256_crypt (puro Python, sem argon2 / bcrypt / Rust)
"""

import os
from datetime import datetime, timedelta
from typing import Dict

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

# Secret para assinar os tokens JWT
SECRET_KEY = os.getenv("AUTH_SECRET", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

# ✅ Usar apenas sha256_crypt (não precisa de bcrypt nem argon2)
pwd_context = CryptContext(
    schemes=["sha256_crypt"],
    deprecated="auto",
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se a palavra-passe em texto simples coincide com o hash armazenado.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Gera um hash seguro da palavra-passe (sha256_crypt).
    """
    return pwd_context.hash(password)


def create_access_token(data: Dict) -> str:
    """
    Cria um token JWT com expiração em ACCESS_TOKEN_EXPIRE_HOURS.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Dict:
    """
    Decodifica e valida um token JWT.
    É esta função que o security.py espera importar.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        )
