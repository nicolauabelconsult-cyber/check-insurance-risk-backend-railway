from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.settings import settings

# Routers (mantém explícito; evita imports circulares)
from app.routers.auth import router as auth_router
from app.routers.entities import router as entities_router
from app.routers.users import router as users_router
from app.routers.sources import router as sources_router
from app.routers.risks import router as risks_router
from app.routers.audit import router as audit_router
from app.routers.public import router as public_router

# ✅ Dashboard (faltava incluir no main)
from app.routers.dashboard import router as dashboard_router

# Novo: diagnostics
from app.routers.diagnostics import router as diagnostics_router


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def create_app() -> FastAPI:
    app = FastAPI(
        title=getattr(settings, "APP_NAME", "Check Insurance Risk API"),
        version=getattr(settings, "APP_VERSION", "1.0.0"),
    )

    # ---------- Middleware (produção-friendly) ----------
    # GZip para responses grandes (PDF/JSON)
    app.add_middleware(GZipMiddleware, minimum_size=1200)

    # Trusted hosts (se não definires, deixa permissivo)
    allowed_hosts = _parse_csv(getattr(settings, "ALLOWED_HOSTS", None))
    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    # CORS (puxa de env se existir; senão abre tudo por enquanto)
    cors_origins = _parse_csv(getattr(settings, "CORS_ORIGINS", None))
    if not cors_origins:
        cors_origins = ["*"]

  app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
    )

    # ---------- Endpoints base ----------
    @app.get("/", include_in_schema=False)
    def root():
        return {"name": app.title, "status": "ok"}

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok"}

    # ---------- Routers ----------
    # Nota: aqui o app já existe, então nunca mais tens NameError
    app.include_router(auth_router)
    app.include_router(entities_router)
    app.include_router(users_router)
    app.include_router(sources_router)
    app.include_router(risks_router)
    app.include_router(audit_router)
    app.include_router(public_router)

    # ✅ Aqui estava a falha: rota /dashboard/summary não existia porque o router não era incluído
    app.include_router(dashboard_router)

    app.include_router(diagnostics_router)

    return app


app = create_app()
