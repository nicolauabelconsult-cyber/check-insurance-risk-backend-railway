from fastapi import Depends, HTTPException
from deps import current_user

def require_roles(*roles):
    def guard(u=Depends(current_user)):
        if u.role not in roles:
            raise HTTPException(403, "Forbidden")
        return u
    return guard
