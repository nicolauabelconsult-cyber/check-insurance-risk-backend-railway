# app/routers/users.py
import secrets
import string
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Entity, User, UserRole, UserStatus
from app.schemas import UserCreate, UserCreateOut, UserEntity, UserOut, UserUpdate
from app.security import hash_password
from app.rbac import role_perms
from app.audit import log
from app.deps import get_current_user, require_perm

router = APIRouter(prefix="/users", tags=["users"])


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


def _gen_temp_password(length: int = 12) -> str:
    """
    Password temporária com:
    - letras + números
    - pelo menos 1 maiúscula, 1 minúscula, 1 dígito
    (sem caracteres chatos tipo espaço)
    """
    if length < 10:
        length = 10

    alphabet = string.ascii_letters + string.digits
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
        ):
            return pwd


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("users:read")),
):
    q = db.query(User)
    # CLIENT_* só vê a sua entidade
    if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        q = q.filter(User.entity_id == u.entity_id)
    return [_user_out(db, x) for x in q.order_by(User.created_at.desc()).all()]


@router.post("", response_model=UserCreateOut)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("users:create")),
):
    # Regras de escopo:
    # - SUPER_ADMIN/ADMIN podem criar em qualquer entity_id (ou sem)
    # - CLIENT_ADMIN só pode criar dentro da sua entity_id
    target_entity_id = body.entity_id

    if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        # CLIENT_ADMIN / CLIENT_ANALYST
        if u.role != UserRole.CLIENT_ADMIN:
            raise HTTPException(status_code=403, detail="Forbidden")
        if not u.entity_id:
            raise HTTPException(status_code=403, detail="Your user has no entity scope")
        target_entity_id = u.entity_id

    # Email único
    exists = db.query(User).filter(User.email == body.email).first()
    if exists:
        raise HTTPException(status_code=409, detail="Email already exists")

    # ✅ Opção 1: gerar password se não vier
    temp_password: str | None = None
    raw_password = (body.password or "").strip()
    if not raw_password:
        temp_password = _gen_temp_password(12)
        raw_password = temp_password

    new = User(
        id=str(uuid.uuid4()),
        name=body.name,
        email=body.email,
        password_hash=hash_password(raw_password),
        role=UserRole(body.role),
        status=UserStatus(body.status or "ACTIVE"),
        entity_id=target_entity_id,
    )
    db.add(new)
    db.commit()
    db.refresh(new)

    log(db, "USER_CREATE", actor=u, entity=u.entity, target_ref=new.email, meta={"role": new.role.value})

    # Devolve user + password temporária (se foi gerada)
    return UserCreateOut(user=_user_out(db, new), temp_password=temp_password)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    body: UserUpdate,
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("users:update")),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # CLIENT_* não mexe fora da sua entidade
    if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        if not u.entity_id or target.entity_id != u.entity_id:
            raise HTTPException(status_code=403, detail="Forbidden")

    if body.name is not None:
        target.name = body.name
    if body.email is not None:
        # garantir unique
        other = db.query(User).filter(User.email == body.email, User.id != target.id).first()
        if other:
            raise HTTPException(status_code=409, detail="Email already exists")
        target.email = body.email
    if body.role is not None:
        target.role = UserRole(body.role)
    if body.status is not None:
        target.status = UserStatus(body.status)

    # entity_id só admin
    if body.entity_id is not None:
        if u.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
            raise HTTPException(status_code=403, detail="Only admin can change entity scope")
        target.entity_id = body.entity_id

    db.commit()
    db.refresh(target)

    log(db, "USER_UPDATE", actor=u, entity=u.entity, target_ref=target.email)

    return _user_out(db, target)


@router.post("/{user_id}/disable", response_model=UserOut)
def disable_user(
    user_id: str,
    db: Session = Depends(get_db),
    u: User = Depends(require_perm("users:disable")),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.status = UserStatus.DISABLED
    db.commit()
    db.refresh(target)

    log(db, "USER_DISABLE", actor=u, entity=u.entity, target_ref=target.email)

    return _user_out(db, target)
