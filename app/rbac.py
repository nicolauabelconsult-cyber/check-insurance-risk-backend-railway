from .models import UserRole

ROLE_PERMS = {
    UserRole.SUPER_ADMIN: {
        "entities:read","entities:create",
        "users:read","users:create","users:update","users:delete",
        "sources:*","risk:*","audit:read"
    },
    UserRole.ADMIN: {
        "entities:read",
        "users:read","users:create","users:update",
        "sources:*","risk:*","audit:read"
    },
    UserRole.CLIENT_ADMIN: {"risk:read","risk:create","risk:pdf:download","sources:read","audit:read","users:read"},
    UserRole.CLIENT_ANALYST: {"risk:read","risk:create","risk:pdf:download","sources:read","audit:read"},
}

def has_perm(role: UserRole, perm: str) -> bool:
    perms = ROLE_PERMS.get(role, set())
    if perm in perms:
        return True
    # wildcard support: sources:* / risk:*
    prefix = perm.split(":")[0] + ":*"
    return prefix in perms
