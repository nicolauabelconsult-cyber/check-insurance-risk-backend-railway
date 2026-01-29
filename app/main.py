from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .settings import settings
from .routers import auth, entities, users

from sqlalchemy.orm import Session
from .db import SessionLocal, Base, engine
from . import models  # IMPORTANTE: garante que as tabelas estão no metadata
from .models import User, UserRole, UserStatus
from .security import hash_password
import uuid

app = FastAPI(title=settings.APP_NAME, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://checkinsurancerisk.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(entities.router)
app.include_router(users.router)


@app.get("/health")
def health():
    return {"status": "ok"}


def ensure_tables():
    # Cria tabelas se ainda não existirem
    Base.metadata.create_all(bind=engine)


def seed_superadmin():
    db: Session = SessionLocal()
    try:
        exists = db.query(User).filter(User.email == settings.SUPERADMIN_EMAIL).first()
        if not exists:
            u = User(
                id=str(uuid.uuid4()),
                name=settings.SUPERADMIN_NAME,
                email=settings.SUPERADMIN_EMAIL,
                password_hash=hash_password(settings.SUPERADMIN_PASSWORD),
                role=UserRole.SUPER_ADMIN,
                status=UserStatus.ACTIVE,
                entity_id=None,
            )
            db.add(u)
            db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    ensure_tables()
    seed_superadmin()
