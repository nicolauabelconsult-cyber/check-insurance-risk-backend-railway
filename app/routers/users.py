import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import get_current_user, require_perm
from ..models import User, Entity, UserRole, UserStatus
from ..schemas import UserOut, UserCreate, UserEntity
from ..security import hash_password
from ..audit import log

router = APIRouter(prefix="/users", tags=["users"])

@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), u=Depends(require_perm("users:read"))):
    q = db.query(User)
    # scoping por entidade (cliente só vê a sua)
    if u.role not in {UserRole.SUPER_ADMIN, UserRole.ADMIN}:
        q = q.filter(User.entity_id == u.entity_id)

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

    # clientes não podem criar users de outras entidades
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
        id=new_user.id,
        name=new_user.name,
        email=new_user.email,
        role=new_user.role.value,
        status=new_user.status.value,
        entity=UserEntity(id=ent.id, name=ent.name),
    )
