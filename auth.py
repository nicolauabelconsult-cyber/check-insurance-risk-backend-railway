# auth.py – versão limpa e compatível com o Settings actual

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import User, UserRole
from schemas import Token, UserRead

# -------------------------------------------------------------------
# CONFIG JWT (compatível com vários formatos de Settings)
# -------------------------------------------------------------------

# Tenta primeiro SECRET_KEY; se não existir, tenta JWT_SECRET_KEY; se não existir, usa "change-me"
SECRET_KEY = getattr(settings, "SECRET_KEY", getattr(settings, "JWT_SECRET_KEY", "change-me"))

# Algoritmo: AUTH_ALGORITHM ou JWT_ALGORITHM, senão HS256
ALGORITHM = getattr(
    settings,
    "AUTH_ALGORITHM",
    getattr(settings, "JWT_ALGORITHM", "HS256"),
)

# Tempo de expiração: se não existir no Settings, usa 12h
ACCESS_TOKEN_EXPIRE_MINUTES = getattr(
    settings,
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    12 * 60,
)

# -------------------------------------------------------------------
# OBJETOS AUXILIARES
# -------------------------------------------------------------------

router = APIRouter(prefix="/auth", tags=["auth"])

# Usar pbkdf2_sha256 em vez de bcrypt
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# -------------------------------------------------------------------
# FUNÇÕES DE PASSWORD
# -------------------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# -------------------------------------------------------------------
# JWT
# -------------------------------------------------------------------

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# -------------------------------------------------------------------
# UTILIZADORES
# -------------------------------------------------------------------

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = get_user_by_username(db, username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# -------------------------------------------------------------------
# DEPENDÊNCIAS DE SEGURANÇA
# -------------------------------------------------------------------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou sessão expirada.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user_by_username(db, username)  # type: ignore[arg-type]
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Utilizador inactivo.")
    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=403,
            detail="Apenas administradores podem aceder.",
        )
    return current_user


# -------------------------------------------------------------------
# ROTAS
# -------------------------------------------------------------------

@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilizador ou palavra-passe incorrectos.",
        )

    access_token = create_access_token(
        {"sub": user.username, "role": user.role},
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserRead)
def read_users_me(
    current_user: User = Depends(get_current_active_user),
):
    return current_user
