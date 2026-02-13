ffrom __future__ import annotations

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.settings import settings
from app.db import get_db
from app.models import Risk
from app.pdfs import make_integrity_hash, make_server_signature

# Routers existentes
from app.routers import auth, entities, users, sources, risks, audit, public

# Novos routers
from app.routers import insurance_sources
from app.routers import compliance_sources


def _parse_origins(value: str | None) -> list[str]:
    if not value:
        return ["*"]
    parts = [x.strip() for x in value.split(",") if x.strip()]
    return parts or ["*"]


origins = _parse_origins(getattr(settings, "CORS_ORIGINS", None))

app = FastAPI(
    title=getattr(settings, "APP_NAME", "Check Insurance Risk API"),
    version=getattr(settings, "APP_VERSION", "v1.0"),
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.get("/health")
def health():
    return {"service": "Check Insurance Risk API", "status": "ok"}


# ------------------------
# Public verification route
# ------------------------
@app.get("/verify/{risk_id}/{hash_value}", response_model=None)
def verify_document(risk_id: str, hash_value: str, db: Session = Depends(get_db)):
    r = db.get(Risk, risk_id)
    if not r:
        raise HTTPException(status_code=404, detail="Risk not found")

    expected = make_integrity_hash(r)
    valid = expected == hash_value
    signature = make_server_signature(expected)

    return {
        "risk_id": risk_id,
        "provided_hash": hash_value,
        "expected_hash": expected,
        "valid": valid,
        "server_signature": signature,
    }


# ------------------------
# Include routers (DEPOIS do app existir)
# ------------------------
app.include_router(auth.router)
app.include_router(entities.router)
app.include_router(users.router)
app.include_router(sources.router)
app.include_router(risks.router)
app.include_router(audit.router)
app.include_router(public.router)

# novos
app.include_router(insurance_sources.router)
app.include_router(compliance_sources.router)
