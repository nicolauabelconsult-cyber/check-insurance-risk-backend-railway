import os
import uuid
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from config import CORS_ORIGINS_LIST, ADMIN_USERNAME, ADMIN_PASSWORD, UPLOAD_DIR
from database import Base, engine
from models import User, InfoSource
from security import hash_password, verify_password, create_access_token
from deps import get_db, get_current_user, require_admin
from schemas import TokenOut, UserRead, UserCreate, UserUpdate, ResetPasswordIn, InfoSourceRead

app = FastAPI(title="Check Insurance Risk API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

    # Seed admin
    from database import SessionLocal
    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.username == ADMIN_USERNAME))
        if not admin:
            db.add(User(
                username=ADMIN_USERNAME,
                name="Administrator",
                email=None,
                role="ADMIN",
                hashed_password=hash_password(ADMIN_PASSWORD),
                is_active=True,
            ))
            db.commit()
    finally:
        db.close()

@app.get("/")
def root():
    return {"message": "API Online — Check Insurance Risk"}

# -------------------------
# AUTH
# -------------------------
@app.post("/api/auth/login", response_model=TokenOut, tags=["auth"])
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == form.username))
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User disabled")
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/api/auth/me", response_model=UserRead, tags=["auth"])
def me(current_user: User = Depends(get_current_user)):
    return current_user

# -------------------------
# USERS (ADMIN)
# -------------------------
@app.get("/api/users", response_model=list[UserRead], tags=["users"])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return db.scalars(select(User).order_by(User.id.desc())).all()

@app.post("/api/users", response_model=UserRead, status_code=201, tags=["users"])
def create_user(payload: UserCreate, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    u = User(
        username=payload.username.strip(),
        name=payload.name,
        email=str(payload.email) if payload.email else None,
        role=payload.role,
        hashed_password=hash_password(payload.password),
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

@app.patch("/api/users/{user_id}", response_model=UserRead, tags=["users"])
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    data = payload.model_dump(exclude_unset=True)

    if "username" in data and data["username"] and data["username"] != u.username:
        if db.scalar(select(User).where(User.username == data["username"])):
            raise HTTPException(status_code=409, detail="Username already exists")

    for k, v in data.items():
        setattr(u, k, v)

    db.add(u)
    db.commit()
    db.refresh(u)
    return u

@app.post("/api/users/{user_id}/reset-password", tags=["users"])
def reset_password(user_id: int, payload: ResetPasswordIn, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if not payload.password or len(payload.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    u.hashed_password = hash_password(payload.password)
    db.add(u)
    db.commit()
    return {"ok": True}

# -------------------------
# INFO SOURCES (EXCEL MVP)
# -------------------------
@app.get("/api/info-sources", response_model=list[InfoSourceRead], tags=["info-sources"])
def list_sources(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return db.scalars(select(InfoSource).order_by(InfoSource.id.desc())).all()

@app.post("/api/info-sources/upload-excel", status_code=201, tags=["info-sources"])
async def upload_excel(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str | None = Form(None),
):
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx/.xls) are supported in this phase.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{safe_name}")

    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)

    row_count = None
    try:
        df = pd.read_excel(path)
        row_count = int(df.shape[0])
    except Exception:
        row_count = None

    src = InfoSource(
        name=name.strip(),
        description=description,
        file_path=path,
        row_count=row_count,
    )
    db.add(src)
    db.commit()
    db.refresh(src)
    return {"id": src.id, "name": src.name, "row_count": src.row_count}

@app.get("/api/info-sources/{source_id}/sample", tags=["info-sources"])
def sample_source(source_id: int, limit: int = 10, db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    src = db.get(InfoSource, source_id)
    if not src:
        raise HTTPException(status_code=404, detail="Source not found")
    if not os.path.exists(src.file_path):
        raise HTTPException(status_code=410, detail="File not available (ephemeral disk). Re-upload required.")

    df = pd.read_excel(src.file_path)
    df = df.head(limit) if limit and limit > 0 else df
    return df.where(pd.notnull(df), None).to_dict(orient="records")

# -------------------------
# DASHBOARD
# -------------------------
@app.get("/api/dashboard/stats", tags=["dashboard"])
def dashboard_stats(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    users_count = db.scalar(select(func.count()).select_from(User)) or 0
    sources_count = db.scalar(select(func.count()).select_from(InfoSource)) or 0
    return {
        "users": users_count,
        "info_sources": sources_count,
        "total_analyses": 0,
        "high_risk": 0,
        "medium_risk": 0,
        "low_risk": 0,
        "critical_risk": 0,
    }
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/version")
def version():
    return {"version": "1.0.0"}
