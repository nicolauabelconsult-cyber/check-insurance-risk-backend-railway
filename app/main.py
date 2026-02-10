# app/main.py
import uuid
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import ProgrammingError

from .settings import settings
from .db import SessionLocal
from .models import User, UserRole, UserStatus
from .security import hash_password
from .deps import get_current_user
from .schemas import UserOut, UserEntity
from .rbac import role_perms
from .audit import log

from .routers import auth, entities, users, sources, risks, audit

app = FastAPI(title=settings.APP_NAME, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(entities.router)
app.include_router(users.router)
app.include_router(sources.router)
app.include_router(risks.router)
app.include_router(audit.router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/auth/me", response_model=UserOut)
def me(u=Depends(get_current_user)):
    ent = u.entity
    return UserOut(
        id=u.id,
        name=u.name,
        email=u.email,
        role=u.role.value,
        status=u.status.value,
        entity=UserEntity(id=ent.id, name=ent.name) if ent else None,
        permissions=role_perms(u.role),
    )

@app.on_event("startup")
def on_startup():
    db: Session = SessionLocal()
    try:
        try:
            u = db.query(User).filter(User.email == settings.SUPERADMIN_EMAIL).first()
        except ProgrammingError:
            return

        if not u:
            u = User(
                id=str(uuid.uuid4()),
                name=settings.SUPERADMIN_NAME,
                email=settings.SUPERADMIN_EMAIL,
                password_hash=hash_password((settings.SUPERADMIN_PASSWORD or "")[:72]),
                role=UserRole.SUPER_ADMIN,
                status=UserStatus.ACTIVE,
                entity_id=None,
            )
            db.add(u)
            db.commit()
            log(db, "SUPERADMIN_CREATED", actor=u, entity=None, target_ref=u.email)
    finally:
        db.close()

@app.get("/debug/cors")
def debug_cors():
    return {"cors": settings.cors_list()}
