from __future__ import annotations
from typing import Dict, Set
from .models import UserRole

ROLE_PERMS: Dict[UserRole, Set[str]] = {
    UserRole.SUPER_ADMIN: {
        "entities:read", "entities:create", "entities:update", "entities:delete",
        "users:read", "users:create", "users:update", "users:delete",
        "sources:read", "sources:upload", "sources:update", "sources:delete",
        "risk:read", "risk:create", "risk:pdf:download",
        "audit:read",
    },
    UserRole.ADMIN: {
        "entities:read",
        "users:read", "users:create", "users:update", "users:delete",
        "sources:read", "sources:upload", "sources:update", "sources:delete",
        "risk:read", "risk:create", "risk:pdf:download",
        "audit:read",
    },
    UserRole.CLIENT_ADMIN: {
        "users:read", "users:create", "users:update",
        "sources:read",
        "risk:read", "risk:create", "risk:pdf:download",
        "audit:read",
    },
    UserRole.CLIENT_ANALYST: {
        "sources:read",
        "risk:read", "risk:create", "risk:pdf:download",
        "audit:read",
    },
}

def has_perm(role: UserRole, perm: str) -> bool:
    return perm in ROLE_PERMS.get(role, set())
