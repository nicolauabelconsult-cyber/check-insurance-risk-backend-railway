from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import Base, engine
from config import *
from models import *
from security import *
from deps import *
from schemas import *
from audit import audit
import os, uuid, pandas as pd

app = FastAPI(title=APP_NAME)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def boot():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if not db.query(User).filter_by(username=ADMIN_USERNAME).first():
        admin = User(username=ADMIN_USERNAME, hashed_password=hash_password(ADMIN_PASSWORD), role="SUPER_ADMIN")
        db.add(admin); db.commit()
    db.close()

@app.post("/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm=Depends(), db:Session=Depends(get_db)):
    u = db.query(User).filter_by(username=form.username).first()
    if not u or not verify_password(form.password, u.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": create_token(u.id)}

@app.get("/auth/me", response_model=UserRead)
def me(u=Depends(current_user)): return u

@app.post("/entities", dependencies=[Depends(require_roles("SUPER_ADMIN"))])
def create_entity(p:EntityCreate, db:Session=Depends(get_db)):
    e = Entity(name=p.name); db.add(e); db.commit(); return e

@app.post("/users", dependencies=[Depends(require_roles("SUPER_ADMIN","PLATFORM_ADMIN"))])
def create_user(p:UserCreate, db:Session=Depends(get_db)):
    u = User(username=p.username, hashed_password=hash_password(p.password), role=p.role, entity_id=p.entity_id)
    db.add(u); db.commit(); return u

@app.post("/sources", dependencies=[Depends(require_roles("SUPER_ADMIN","PLATFORM_ADMIN"))])
def upload_source(file:UploadFile=File(...), db:Session=Depends(get_db), u=Depends(current_user)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = f"{UPLOAD_DIR}/{uuid.uuid4()}_{file.filename}"
    with open(path,"wb") as f: f.write(file.file.read())
    s = InfoSource(name=file.filename, file_path=path, uploaded_by=u.id)
    db.add(s); db.commit(); return s

@app.post("/analyses", response_model=AnalysisRead, dependencies=[Depends(require_roles("CLIENT_ADMIN","CLIENT_ANALYST"))])
def analyse(p:AnalysisCreate, db:Session=Depends(get_db), u=Depends(current_user)):
    score = len(p.subject_name)*5
    level = "LOW" if score<30 else "MEDIUM" if score<60 else "HIGH"
    a = Analysis(entity_id=u.entity_id, subject_name=p.subject_name, risk_score=score, risk_level=level, created_by=u.id)
    db.add(a); db.commit(); return a
