from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..db.deps import get_db
from ..db.models import User
from ..schemas.users import UserRead, UserCreate, UserUpdate
from ..core.deps import require_admin
from ..services.users import get_user_by_username, create_user, update_user

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db), _admin = Depends(require_admin)):
    users = db.scalars(select(User).order_by(User.id.desc())).all()
    return users

@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db), _admin = Depends(require_admin)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return u

@router.post("", response_model=UserRead, status_code=201)
def create_user_endpoint(payload: UserCreate, db: Session = Depends(get_db), _admin = Depends(require_admin)):
    existing = get_user_by_username(db, payload.username)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    u = create_user(
        db,
        username=payload.username.strip(),
        password=payload.password,
        role=payload.role,
        name=payload.name,
        email=str(payload.email) if payload.email else None,
    )
    return u

@router.patch("/{user_id}", response_model=UserRead)
def update_user_endpoint(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), _admin = Depends(require_admin)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.username and payload.username != u.username:
        if get_user_by_username(db, payload.username):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    data = payload.model_dump(exclude_unset=True)
    u = update_user(db, u, **data)
    return u
