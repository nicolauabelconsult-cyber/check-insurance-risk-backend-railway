from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from config import SECRET_KEY, ACCESS_TOKEN_EXPIRE_HOURS

ALGORITHM = "HS256"
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p: str) -> str:
    return pwd.hash(p)

def verify_password(p: str, hashed: str) -> bool:
    return pwd.verify(p, hashed)

def create_access_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "exp": exp}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
