from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from jose import jwt
from config import SECRET_KEY
from database import SessionLocal
from models import User

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def current_user(token: str = Depends(lambda: None), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        u = db.get(User, int(payload["sub"]))
        if not u or not u.is_active:
            raise Exception()
        return u
    except:
        raise HTTPException(401, "Invalid token")
