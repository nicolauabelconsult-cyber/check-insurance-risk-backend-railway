from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth import verify_token
from database import execute_query
from models import RoleEnum, UserInfo

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserInfo:
    try:
        token = credentials.credentials
        payload = verify_token(token)
        query = """
            SELECT id, username, email, role, is_active, last_login, created_at
            FROM users WHERE id = %s AND is_active = true
        """
        users = execute_query(query, (payload["id"],))
        if not users:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado",
            )
        user = users[0]
        return UserInfo(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            role=user["role"],
            last_login=user["last_login"],
            created_at=user["created_at"],
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )


async def get_admin_user(
    current_user: UserInfo = Depends(get_current_user),
) -> UserInfo:
    if current_user.role != RoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: permissões de administrador necessárias",
        )
    return current_user
