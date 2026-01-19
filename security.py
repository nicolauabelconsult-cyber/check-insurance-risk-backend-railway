from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt

from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _bcrypt_safe(p: str) -> str:
    if not p:
        return ""
    b = p.encode("utf-8")
    return b[:72].decode("utf-8", errors="ignore")

def hash_password(p: str) -> str:
    return pwd.hash(_bcrypt_safe(p))

def verify_password(p: str, hashed: str) -> bool:
    return pwd.verify(_bcrypt_safe(p), hashed)

def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
