from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .db import get_db
from .security import decode_token
from .models import User, UserStatus
from .rbac import has_perm

bearer = HTTPBearer()

def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(cred.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    u = db.get(User, user_id)
    if not u or u.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="User disabled")
    return u

def require_perm(perm: str):
    def checker(u: User = Depends(get_current_user)):
        if not has_perm(u.role, perm):
            raise HTTPException(status_code=403, detail="Forbidden")
        return u
    return checker



def _role_val(u) -> str:
    return getattr(getattr(u, "role", None), "value", getattr(u, "role", None)) or ""

def ensure_entity_scope(u: User, entity_id: str) -> None:
    role = _role_val(u)
    if role == "SUPER_ADMIN":
        return
    if not getattr(u, "entity_id", None):
        raise HTTPException(status_code=403, detail="Entity scope missing")
    if u.entity_id != entity_id:
        raise HTTPException(status_code=403, detail="Forbidden (entity scope)")

def resolve_entity_id(u: User, requested_entity_id: str | None, *, require: bool = True) -> str | None:
    """Resolve and enforce tenant scope.
    - SUPER_ADMIN: may choose any entity_id; if not provided returns None unless require=True.
    - Others: forced to u.entity_id; if requested provided and differs -> 403.
    """
    role = _role_val(u)
    if role == "SUPER_ADMIN":
        if requested_entity_id:
            return requested_entity_id
        if require:
            raise HTTPException(status_code=400, detail="entity_id required")
        return None

    if not getattr(u, "entity_id", None):
        raise HTTPException(status_code=403, detail="Entity scope missing")
    if requested_entity_id and requested_entity_id != u.entity_id:
        raise HTTPException(status_code=403, detail="Forbidden (entity scope)")
    return u.entity_id
