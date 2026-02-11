# app/rbac.py
from .models import UserRole

PERMS_BY_ROLE = {
    UserRole.SUPER_ADMIN: {
        "entities:read", "entities:create", "entities:update",
        "users:read", "users:create", "users:update", "users:delete",
        "users:disable", "users:reset_password",
        "sources:read", "sources:create", "sources:upload", "sources:update", "sources:delete",
        "risk:read", "risk:create", "risk:confirm", "risk:pdf:download",
        "audit:read",
    },
    UserRole.ADMIN: {
        "entities:read",
        "users:read", "users:create", "users:update",
        "users:disable", "users:reset_password",
        "sources:read", "sources:create", "sources:upload", "sources:update",
        "risk:read", "risk:create", "risk:confirm", "risk:pdf:download",
        "audit:read",
    },
    UserRole.CLIENT_ADMIN: {
        "users:read", "users:create", "users:update",
        "users:disable", "users:reset_password",
        "sources:read",
        "risk:read", "risk:create", "risk:confirm", "risk:pdf:download",
        "audit:read",
    },
    UserRole.CLIENT_ANALYST: {
        "sources:read",
        "risk:read", "risk:create", "risk:confirm", "risk:pdf:download",
        "audit:read",
    },
}

# ✅ compatibilidade com imports antigos
ROLE_PERMS = PERMS_BY_ROLE

def has_perm(role: UserRole, perm: str) -> bool:
    return perm in PERMS_BY_ROLE.get(role, set())

def role_perms(role: UserRole) -> list[str]:
    return sorted(list(PERMS_BY_ROLE.get(role, set())))
