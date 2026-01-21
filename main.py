import os, uuid, pandas as pd
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from config import *
from database import Base, engine, SessionLocal
from models import *
from schemas import *
from security import *
from deps import *
from rbac import *
from pdf import generate_analysis_pdf
from audit import audit

app = FastAPI(title=APP_NAME)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def boot():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if not db.query(User).filter_by(username=ADMIN_USERNAME).first():
        db.add(User(username=ADMIN_USERNAME, hashed_password=hash_password(ADMIN_PASSWORD), role="SUPER_ADMIN"))
        db.commit()
    db.close()

@app.post("/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    u = db.query(User).filter_by(username=form.username).first()
    if not u or not verify_password(form.password, u.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    audit(db, "LOGIN", u)
    return {"access_token": create_token(u.id)}

@app.get("/auth/me", response_model=UserRead)
def me(u=Depends(current_user)): return u
