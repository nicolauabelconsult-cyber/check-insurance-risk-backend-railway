from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .security import decode_token
from .models import User, UserStatus
from .rbac import has_perm

bearer = HTTPBearer(auto_error=False)

def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not cred or not cred.credentials:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        payload = decode_token(cred.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    # se o token tiver type, valida
    token_type = payload.get("type")
    if token_type and token_type != "access":
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
