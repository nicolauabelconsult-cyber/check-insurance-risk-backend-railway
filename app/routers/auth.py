from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import traceback

from ..db import get_db
from ..schemas import LoginIn, LoginOut
from ..models import User, UserStatus
from ..security import verify_password, create_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=LoginOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    try:
        u = db.query(User).filter(User.email == data.email).first()
        if not u or u.status != UserStatus.ACTIVE:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not verify_password(data.password, u.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        access = create_token(sub=u.id, token_type="access", role=u.role.value, entity_id=u.entity_id)
        refresh = create_token(sub=u.id, token_type="refresh", role=u.role.value, entity_id=u.entity_id)

        return {
            "access_token": access,
            "refresh_token": refresh,
            "user": {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "role": u.role.value,
                "status": u.status.value,
                "entity": None,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        print("LOGIN_CRASH:", repr(e))
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Login error (see server logs)")
