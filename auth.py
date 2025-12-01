from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserRole
from schemas import Token, UserRead
from config import settings

# -------------------------------------------------------------------
# ROUTER
# -------------------------------------------------------------------
router = APIRouter(prefix="/auth", tags=["auth"])

# -------------------------------------------------------------------
# PASSWORD HASHING (SEM BCRYPT)
# -------------------------------------------------------------------
# Usamos pbkdf2_sha256 para evitar problemas com bcrypt no Render.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# OAuth2 – o frontend faz login em /api/auth/login
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/auth/login"
)


# -------------------------------------------------------------------
# UTILITÁRIOS DE PASSWORD
# -------------------------------------------------------------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a password corresponde ao hash armazenado."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Gera o hash da password.
    (Usado também pelo seed_admin.py para criar o admin inicial.)
    """
    return pwd_context.hash(password)


# -------------------------------------------------------------------
# JWT
# -------------------------------------------------------------------
def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    """
    Cria um token JWT com:
    - sub: username
    - role: perfil do utilizador
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


# -------------------------------------------------------------------
# HELPERS DE UTILIZADOR
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
# DEPENDENCIES – CURRENT USER / ADMIN
# -------------------------------------------------------------------
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Valida o token JWT e devolve o utilizador actual.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou sessão expirada.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user_by_username(db, username)
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
            detail="Apenas administradores podem aceder a esta funcionalidade.",
        )
    return current_user


# -------------------------------------------------------------------
# ROTAS DE AUTENTICAÇÃO
# -------------------------------------------------------------------
@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Endpoint de login:
    - recebe username + password via form-data (padrão OAuth2)
    - devolve access_token (JWT) + token_type
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nome de utilizador ou palavra-passe incorrectos.",
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserRead)
def read_users_me(
    current_user: User = Depends(get_current_active_user),
):
    """
    Devolve os dados do utilizador autenticado.
    Usado pelo frontend para mostrar o nome / role.
    """
    return current_user
