from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt

from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

# Sem bcrypt -> evita bug de versão e o limite de 72 bytes
pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(p: str) -> str:
    return pwd.hash(p or "")


def verify_password(p: str, hashed: str) -> bool:
    return pwd.verify(p or "", hashed)


def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
