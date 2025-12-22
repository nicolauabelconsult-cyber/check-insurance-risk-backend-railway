from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db.models import User
from ..core.security import hash_password, verify_password
from ..core.config import settings

def get_user_by_username(db: Session, username: str):
    return db.scalar(select(User).where(User.username == username))

def get_user_by_id(db: Session, user_id: int):
    return db.get(User, user_id)

def authenticate(db: Session, username: str, password: str):
    u = get_user_by_username(db, username)
    if not u:
        return None
    if not verify_password(password, u.hashed_password):
        return None
    return u

def ensure_admin_seed(db: Session):
    admin = get_user_by_username(db, settings.ADMIN_USERNAME)
    if admin:
        return admin
    admin = User(
        username=settings.ADMIN_USERNAME,
        name="Administrator",
        email=None,
        role="ADMIN",
        hashed_password=hash_password(settings.ADMIN_PASSWORD),
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin

def create_user(db: Session, username: str, password: str, role: str, name=None, email=None):
    u = User(
        username=username,
        name=name,
        email=email,
        role=role,
        hashed_password=hash_password(password),
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

def update_user(db: Session, u: User, **fields):
    for k, v in fields.items():
        if v is not None:
            setattr(u, k, v)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u
