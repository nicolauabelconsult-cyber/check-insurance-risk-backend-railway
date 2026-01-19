import os
import uuid
import pandas as pd

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from config import APP_NAME, CORS_ORIGINS, ADMIN_USERNAME, ADMIN_PASSWORD, UPLOAD_DIR
from database import Base, engine, SessionLocal
from models import User, Entity, InfoSource, Analysis
from security import hash_password, verify_password, create_token
from deps import get_db, current_user, require_roles
from schemas import TokenOut, UserRead, EntityCreate, UserCreate, AnalysisCreate, AnalysisRead

app = FastAPI(title=APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def boot():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        admin = db.query(User).filter_by(username=ADMIN_USERNAME).first()
        if not admin:
            admin = User(
                username=ADMIN_USERNAME,
                hashed_password=hash_password(ADMIN_PASSWORD),
                role="SUPER_ADMIN",
                entity_id=None,
                is_active=True,
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()

@app.get("/")
def root():
    return {"message": "API Online — Check Insurance Risk"}

# -------------------------
# AUTH
# -------------------------
@app.post("/auth/login", response_model=TokenOut, tags=["auth"])
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    u = db.query(User).filter_by(username=form.username).first()
    if not u or not verify_password(form.password, u.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not u.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User disabled")

    return {"access_token": create_token(u.id), "token_type": "bearer"}

@app.get("/auth/me", response_model=UserRead, tags=["auth"])
def me(u: User = Depends(current_user)):
    return u

# -------------------------
# ENTITIES (SUPER ADMIN)
# -------------------------
@app.post("/entities", tags=["entities"])
def create_entity(
    p: EntityCreate,
    db: Session = Depends(get_db),
    _su: User = Depends(require_roles("SUPER_ADMIN")),
):
    e = Entity(name=p.name.strip(), active=True)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e

# -------------------------
# USERS (INTERNAL ADMINS)
# -------------------------
@app.post("/users", tags=["users"])
def create_user(
    p: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("SUPER_ADMIN", "PLATFORM_ADMIN")),
):
    if db.query(User).filter_by(username=p.username).first():
        raise HTTPException(status_code=409, detail="Username already exists")

    u = User(
        username=p.username.strip(),
        hashed_password=hash_password(p.password),
        role=p.role,
        entity_id=p.entity_id,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

# -------------------------
# SOURCES (EXCEL/PDF) — INTERNAL ONLY
# -------------------------
@app.post("/sources", tags=["sources"])
def upload_source(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    u: User = Depends(require_roles("SUPER_ADMIN", "PLATFORM_ADMIN")),
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe = file.filename.replace("/", "_").replace("\\", "_")
    path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{safe}")

    with open(path, "wb") as f:
        f.write(file.file.read())

    s = InfoSource(name=file.filename, file_path=path, uploaded_by=u.id)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

# -------------------------
# ANALYSES (CLIENT)
# -------------------------
@app.post("/analyses", response_model=AnalysisRead, tags=["analyses"])
def analyse(
    p: AnalysisCreate,
    db: Session = Depends(get_db),
    u: User = Depends(require_roles("CLIENT_ADMIN", "CLIENT_ANALYST")),
):
    if not u.entity_id:
        raise HTTPException(status_code=400, detail="User has no entity_id assigned")

    score = len(p.subject_name.strip()) * 5
    level = "LOW" if score < 30 else "MEDIUM" if score < 60 else "HIGH"

    a = Analysis(
        entity_id=u.entity_id,
        subject_name=p.subject_name.strip(),
        risk_score=score,
        risk_level=level,
        created_by=u.id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)

    return AnalysisRead(
        id=a.id,
        subject_name=a.subject_name,
        risk_score=a.risk_score,
        risk_level=a.risk_level,
    )
