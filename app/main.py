from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.settings import settings

from app.routers.auth import router as auth_router
from app.routers.entities import router as entities_router
from app.routers.users import router as users_router
from app.routers.sources import router as sources_router
from app.routers.risks import router as risks_router
from app.routers.audit import router as audit_router
from app.routers.public import router as public_router
from app.routers.dashboard import router as dashboard_router
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

    # gzip (bom para JSON grandes)
    app.add_middleware(GZipMiddleware, minimum_size=1200)

    # CORS
    cors_origins = _parse_csv(getattr(settings, "CORS_ORIGINS", None))
    if not cors_origins:
        # ✅ Produção: domínio oficial
        cors_origins = [
            "https://checkinsurancerisk.com",
            "https://www.checkinsurancerisk.com",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", include_in_schema=False)
    def root():
        return {"name": app.title, "status": "ok"}

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok"}

    # Routers
    app.include_router(auth_router)
    app.include_router(entities_router)
    app.include_router(users_router)
    app.include_router(sources_router)
    app.include_router(risks_router)
    app.include_router(audit_router)
    app.include_router(public_router)
    app.include_router(dashboard_router)
    app.include_router(diagnostics_router)

    return app


app = create_app()
