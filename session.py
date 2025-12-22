import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from ..core.config import settings

def _sqlite_url():
    os.makedirs("data", exist_ok=True)
    return "sqlite:///./data/app.db"

DATABASE_URL = settings.DATABASE_URL or _sqlite_url()

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def init_db():
    from . import models  # noqa
    Base.metadata.create_all(bind=engine)

    from ..services.users import ensure_admin_seed
    db = SessionLocal()
    try:
        ensure_admin_seed(db)
    finally:
        db.close()
