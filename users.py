# users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas import UserCreate, UserRead
from models import User, UserRole
from auth import get_current_admin, get_password_hash

router = APIRouter(prefix="/users", tags=["Users"])

# ----------------------------------------------------------
# Criar utilizador
# ----------------------------------------------------------
@router.post("/", response_model=UserRead)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    # Verificar se já existe
    existing = (
        db.query(User)
        .filter((User.email == data.email) | (User.username == data.username))
        .first()
    )
    if existing:
        raise HTTPException(400, "Já existe utilizador com este email ou username.")

    user = User(
        username=data.username,
        email=data.email,
        role=data.role,
        is_active=True,
        hashed_password=get_password_hash(data.password),
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ----------------------------------------------------------
# Listar utilizadores
# ----------------------------------------------------------
@router.get("/", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    return db.query(User).order_by(User.id.asc()).all()


# ----------------------------------------------------------
# Apagar utilizador
# ----------------------------------------------------------
@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Utilizador não encontrado.")

    db.delete(user)
    db.commit()
    return {"deleted": True}
