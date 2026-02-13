from __future__ import annotations

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.settings import settings
from app.db import engine, Base, get_db

# Routers principais
from app.routers import auth, entities, users, sources, risks, audit

# Router Excel seguros (se existir)
try:
    from app.routers import insurance_sources
    HAS_INSURANCE = True
except Exception:
    HAS_INSURANCE = False

# RBAC (compatível com versões antigas)
try:
    from app.rbac import ROLE_PERMS
except Exception:
    try:
        from app.rbac import PERMS_BY_ROLE as ROLE_PERMS
    except Exception:
        ROLE_PERMS = {}

from app.models import Risk


# =========================================================
# Inicialização
# =========================================================

app = FastAPI(
    title="Check Insurance Risk API",
    version=getattr(settings, "APP_VERSION", "1.0"),
    docs_url="/docs",
    redoc_url="/redoc",
)


# =========================================================
# CORS
# =========================================================

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://checkinsurancerisk.com",
    getattr(settings, "FRONTEND_URL", None),
]

origins = [o for o in origins if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# Routers
# =========================================================

app.include_router(auth.router)
app.include_router(entities.router)
app.include_router(users.router)
app.include_router(sources.router)
app.include_router(risks.router)
app.include_router(audit.router)

if HAS_INSURANCE:
    app.include_router(insurance_sources.router)


# =========================================================
# Health check
# =========================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": "Check Insurance Risk",
        "version": getattr(settings, "APP_VERSION", "1.0"),
        "env": getattr(settings, "APP_ENV", "production"),
    }


# =========================================================
# QR Verification Endpoint
# =========================================================

@app.get("/verify/{risk_id}/{hash_value}")
def verify_document(risk_id: str, hash_value: str, db: Session = next(get_db())):
    risk = db.get(Risk, risk_id)
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    from app.pdfs import make_integrity_hash

    current_hash = make_integrity_hash(risk)

    return {
        "risk_id": risk_id,
        "valid": current_hash == hash_value,
        "expected_hash": current_hash,
        "provided_hash": hash_value,
    }


# =========================================================
# Root
# =========================================================

@app.get("/")
def root():
    return {
        "message": "Check Insurance Risk API",
        "docs": "/docs",
        "status": "running",
    }


# =========================================================
# Error handler global
# =========================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc),
        },
    )
