from .models import UserRole

ROLE_PERMS = {
    UserRole.SUPER_ADMIN: {
        "entities:read","entities:create","entities:update","entities:disable",
        "users:read","users:create","users:update","users:disable","users:delete","users:reset_password",
        "sources:read","sources:create","sources:update","sources:disable","sources:delete",
        "risk:read","risk:create","risk:pdf:download",
        "audit:read","audit:print",
    },
    UserRole.ADMIN: {
        "entities:read",
        "users:read","users:create","users:update","users:disable","users:reset_password",
        "sources:read","sources:create","sources:update","sources:disable",
        "risk:read","risk:create","risk:pdf:download",
        "audit:read","audit:print",
    },
    UserRole.CLIENT_ADMIN: {
        "users:read","users:create","users:update","users:disable","users:reset_password",
        "sources:read","sources:create","sources:update","sources:disable",
        "risk:read","risk:create","risk:pdf:download",
        "audit:read","audit:print",
    },
    UserRole.CLIENT_ANALYST: {
        "sources:read",
        "risk:read","risk:create","risk:pdf:download",
        "audit:read","audit:print",
    },
}

def has_perm(role: UserRole, perm: str) -> bool:
    perms = ROLE_PERMS.get(role, set())
    if perm in perms:
        return True
    prefix = perm.split(":")[0] + ":*"
    return prefix in perms
