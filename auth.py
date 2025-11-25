from datetime import datetime, timedelta
import os
from typing import Optional

from fastapi import HTTPException, status, Depends
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app import models
from app.schemas import TokenData

SECRET_KEY = os.getenv("AUTH_SECRET", settings.AUTH_SECRET)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = settings.ACCESS_TOKEN_EXPIRE_HOURS

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta_hours: int = ACCESS_TOKEN_EXPIRE_HOURS) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=expires_delta_hours)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role", "ANALYST")
        if username is None:
            raise JWTError("Missing username")
        return TokenData(username=username, role=role)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    user = db.query(models.User).filter(
        (models.User.username == username) | (models.User.email == username)
    ).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(lambda authorization: authorization)
):
    # Token virá via Header Authorization: Bearer <token>
    from fastapi import Header

    auth_header: str = Header(default=None, alias="Authorization")  # type: ignore

    if not auth_header:
        raise HTTPException(status_code=401, detail="Credenciais não fornecidas")

    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Formato de token inválido")

    token_data = decode_token(token)
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilizador não encontrado")

    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return user
