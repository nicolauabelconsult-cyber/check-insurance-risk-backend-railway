# app/rbac.py
from __future__ import annotations

from app.models import UserRole

# Fonte única de verdade das permissões por role
PERMS_BY_ROLE = {
    UserRole.SUPER_ADMIN: {
        # ✅ Dashboard
        "dashboard:read",
        # Core
        "entities:read",
        "entities:create",
        "entities:update",
        "users:read",
        "users:create",
        "users:update",
        "users:disable",
        "users:reset_password",
        "sources:read",
        "sources:create",
        "sources:update",
        "sources:disable",
        "risk:read",
        "risk:create",
        "risk:confirm",
        "risk:pdf:download",
        "audit:read",
        "admin:dashboard",
        "compliance:write",
        "insurance:upload",
    },
    UserRole.ADMIN: {
        # ✅ Dashboard
        "dashboard:read",
        # Core
        "entities:read",
        "users:read",
        "users:create",
        "users:update",
        "users:disable",
        "users:reset_password",
        "sources:read",
        # Produção V1: ADMIN não cria fontes (apenas SUPER_ADMIN)
        "sources:update",
        "sources:disable",
        "risk:read",
        "risk:create",
        "risk:confirm",
        "risk:pdf:download",
        "audit:read",
        "admin:dashboard",
        "compliance:write",
        "insurance:upload",
    },
    UserRole.CLIENT_ADMIN: {
        "users:read",
        "users:create",
        "users:update",
        "sources:read",
        "risk:read",
        "risk:create",
        "risk:confirm",
        "risk:pdf:download",
        # Cliente não vê auditoria
    },
    UserRole.CLIENT_ANALYST: {
        "sources:read",
        "risk:read",
        "risk:create",
        "risk:confirm",
        "risk:pdf:download",
        # Cliente não vê auditoria
    },
}

# Compatibilidade com imports antigos (se algum ficheiro usar ROLE_PERMS)
ROLE_PERMS = PERMS_BY_ROLE


def _normalize_role(role) -> UserRole | None:
    """
    Aceita:
      - UserRole
      - string "SUPER_ADMIN" / "super_admin" / "Super_Admin"
    Devolve UserRole ou None se inválido.
    """
    if role is None:
        return None

    if isinstance(role, UserRole):
        return role

    if isinstance(role, str):
        # Normaliza "super_admin" -> "SUPER_ADMIN"
        role_norm = role.strip().upper()
        try:
            return UserRole(role_norm)
        except Exception:
            return None

    return None


def has_perm(role, perm: str) -> bool:
    r = _normalize_role(role)
    if r is None:
        return False
    return perm in PERMS_BY_ROLE.get(r, set())


def role_perms(role) -> list[str]:
    r = _normalize_role(role)
    if r is None:
        return []
    return sorted(PERMS_BY_ROLE.get(r, set()))
