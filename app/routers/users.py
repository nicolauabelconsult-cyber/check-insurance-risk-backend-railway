import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_perm
from app.models import User, Entity, UserRole, UserStatus
from app.schemas import UserOut, UserCreate, UserUpdate, ResetPasswordIn, UserEntity
from app.security import hash_password
from app.audit import log

router = APIRouter(prefix="/users", tags=["users"])

def _scope_query(q, current: User):
    if current.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        return q
    return q.filter(User.entity_id == current.entity_id)

@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), u=Depends(require_perm("users:read"))):
    q = _scope_query(db.query(User), u)
    users = q.order_by(User.name.asc()).all()

    out = []
    for x in users:
        ent = x.entity
        out.append(UserOut(
            id=x.id, name=x.name, email=x.email, role=x.role.value, status=x.status.value,
            entity=UserEntity(id=ent.id, name=ent.name) if ent else None
        ))
    return out

@router.post("", response_model=UserOut)
def create_user(body: UserCreate, db: Session = Depends(get_db), u=Depends(require_perm("users:create"))):
    ent = db.get(Entity, body.entity_id)
    if not ent:
        raise HTTPException(status_code=400, detail="Invalid entity_id")

    if u.role not in {UserRole.SUPER_ADMIN, UserRole.ADMIN} and body.entity_id != u.entity_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    exists = db.query(User).filter(User.email == body.email).first()
    if exists:
        raise HTTPException(status_code=409, detail="Email already exists")

    new_user = User(
        id=str(uuid.uuid4()),
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        role=UserRole(body.role),
        status=UserStatus.ACTIVE,
        entity_id=ent.id,
    )
    db.add(new_user)
    db.commit()

    log(db, "USER_CREATED", actor=u, entity=ent, target_ref=body.email, meta={"role": body.role})

    return UserOut(
        id=new_user.id, name=new_user.name, email=new_user.email,
        role=new_user.role.value, status=new_user.status.value,
        entity=UserEntity(id=ent.id, name=ent.name),
    )

@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: str, body: UserUpdate, db: Session = Depends(get_db), u=Depends(require_perm("users:update"))):
    q = _scope_query(db.query(User), u)
    target = q.filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Not found")

    if body.name is not None:
        target.name = body.name
    if body.role is not None:
        # clientes não podem promover para SUPER_ADMIN/ADMIN
        if u.role not in {UserRole.SUPER_ADMIN, UserRole.ADMIN} and body.role in {UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value}:
            raise HTTPException(status_code=403, detail="Forbidden role")
        target.role = UserRole(body.role)
    if body.status is not None:
        target.status = UserStatus(body.status)

    db.commit()
    log(db, "USER_UPDATED", actor=u, entity=target.entity, target_ref=target.email)
    ent = target.entity
    return UserOut(
        id=target.id, name=target.name, email=target.email,
        role=target.role.value, status=target.status.value,
        entity=UserEntity(id=ent.id, name=ent.name) if ent else None
    )

@router.post("/{user_id}/disable", response_model=UserOut)
def disable_user(user_id: str, db: Session = Depends(get_db), u=Depends(require_perm("users:disable"))):
    q = _scope_query(db.query(User), u)
    target = q.filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Not found")
    target.status = UserStatus.DISABLED
    db.commit()
    log(db, "USER_DISABLED", actor=u, entity=target.entity, target_ref=target.email)
    ent = target.entity
    return UserOut(
        id=target.id, name=target.name, email=target.email,
        role=target.role.value, status=target.status.value,
        entity=UserEntity(id=ent.id, name=ent.name) if ent else None
    )

@router.post("/{user_id}/reset-password")
def reset_password(user_id: str, body: ResetPasswordIn, db: Session = Depends(get_db), u=Depends(require_perm("users:reset_password"))):
    q = _scope_query(db.query(User), u)
    target = q.filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Not found")

    target.password_hash = hash_password(body.new_password)
    db.commit()
    log(db, "USER_PASSWORD_RESET", actor=u, entity=target.entity, target_ref=target.email)
    return {"ok": True}
