from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, UserStatus
from ..security import verify_password, create_token
from ..schemas import LoginIn, LoginOut, UserOut, UserEntity
from ..settings import settings
from ..audit import log

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == payload.email).first()
    if not u or u.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    ent = u.entity

    access = create_token(
        sub=u.id,
        token_type="access",
        role=u.role.value,
        entity_id=u.entity_id,
        expires_minutes=settings.JWT_ACCESS_MINUTES,
    )

    refresh = create_token(
        sub=u.id,
        token_type="refresh",
        role=u.role.value,
        entity_id=u.entity_id,
        refresh_days=settings.JWT_REFRESH_DAYS,
    )

    out = UserOut(
        id=u.id,
        name=u.name,
        email=u.email,
        role=u.role.value,
        status=u.status.value,
        entity=UserEntity(id=ent.id, name=ent.name) if ent else None
    )

    log(db, "LOGIN_SUCCESS", actor=u, entity=ent, target_ref=u.email)
    return LoginOut(access_token=access, refresh_token=refresh, user=out)
