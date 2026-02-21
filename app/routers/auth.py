import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Entity, User, UserStatus
from app.schemas import LoginIn, LoginOut, RefreshIn, TokenOut, UserEntity, UserOut
from app.security import create_token, decode_token, verify_password
from app.settings import settings
from app.rbac import role_perms
from app.audit import log
from app.deps import get_current_user


router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(db: Session, u: User) -> UserOut:
    ent = db.get(Entity, u.entity_id) if u.entity_id else None
    return UserOut(
        id=u.id,
        name=u.name,
        email=u.email,
        role=u.role.value,
        status=u.status.value,
        entity=UserEntity(id=ent.id, name=ent.name) if ent else None,
        permissions=role_perms(u.role),
    )


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == body.email).first()
    if not u or u.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(body.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access = create_token(
        sub=u.id,
        token_type="access",
        role=u.role.value,
        entity_id=u.entity_id,
        expires_minutes=settings.JWT_ACCESS_MINUTES,
        refresh_days=settings.JWT_REFRESH_DAYS,
    )
    refresh = create_token(
        sub=u.id,
        token_type="refresh",
        role=u.role.value,
        entity_id=u.entity_id,
        expires_minutes=settings.JWT_ACCESS_MINUTES,
        refresh_days=settings.JWT_REFRESH_DAYS,
    )

    log(db, "AUTH_LOGIN", actor=u, entity=u.entity, target_ref=u.email)

    return LoginOut(access_token=access, refresh_token=refresh, user=_user_out(db, u))


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    u = db.get(User, user_id)
    if not u or u.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="User disabled")

    access = create_token(
        sub=u.id,
        token_type="access",
        role=u.role.value,
        entity_id=u.entity_id,
        expires_minutes=settings.JWT_ACCESS_MINUTES,
        refresh_days=settings.JWT_REFRESH_DAYS,
    )

    log(db, "AUTH_REFRESH", actor=u, entity=u.entity, target_ref=u.email)

    return TokenOut(access_token=access)


@router.get("/me", response_model=UserOut)
def me(db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    return _user_out(db, u)
