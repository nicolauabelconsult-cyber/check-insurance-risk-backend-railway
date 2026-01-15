from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import jwt
from database import SessionLocal
from config import SECRET_KEY, ALGORITHM
from models import User

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def current_user(token=Depends(oauth2), db: Session=Depends(get_db)):
    try:
        uid = int(jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"])
    except:
        raise HTTPException(401, "Invalid token")
    user = db.get(User, uid)
    if not user or not user.is_active:
        raise HTTPException(401, "Inactive user")
    return user

def require_roles(*roles):
    def guard(user=Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(403, "Forbidden")
        return user
    return guard
