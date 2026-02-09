from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import LoginIn, LoginOut, UserOut, UserEntity
from ..models import User, UserStatus
from ..security import verify_password, create_token
from ..deps import get_current_user
from ..rbac import role_perms

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=LoginOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == data.email).first()
    if not u or u.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(data.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access = create_token(sub=u.id, token_type="access", role=u.role.value, entity_id=u.entity_id)
    refresh = create_token(sub=u.id, token_type="refresh", role=u.role.value, entity_id=u.entity_id)

    ent = u.entity
    return {
        "access_token": access,
        "refresh_token": refresh,
        "user": {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role.value,
            "status": u.status.value,
            "entity": {"id": ent.id, "name": ent.name} if ent else None,
            "permissions": role_perms(u.role),
        },
    }

@router.get("/me", response_model=UserOut)
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
