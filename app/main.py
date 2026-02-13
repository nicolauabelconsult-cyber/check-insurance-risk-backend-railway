from __future__ import annotations

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.settings import settings
from app.db import get_db
from app.models import Risk
from app.pdfs import make_integrity_hash, make_server_signature

from app.routers.auth import router as auth_router
from app.routers.entities import router as entities_router
from app.routers.users import router as users_router
from app.routers.sources import router as sources_router
from app.routers.risks import router as risks_router
from app.routers.audit import router as audit_router
from app.routers.public import router as public_router

# Se existirem no teu projecto, podes incluir:
# from app.routers.insurance_sources import router as insurance_sources_router
# from app.routers.compliance_sources import router as compliance_sources_router


def _parse_origins(value: str | None) -> list[str]:
    if not value:
        return ["*"]
    parts = [x.strip() for x in value.split(",") if x.strip()]
    return parts or ["*"]


app = FastAPI(
    title=getattr(settings, "APP_NAME", "Check Insurance Risk API"),
    version=getattr(settings, "APP_VERSION", "v1.0"),
)

origins = _parse_origins(getattr(settings, "CORS_ORIGINS", None))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # necessário para download PDF
)


@app.get("/health")
def health():
    return {"service": "Check Insurance Risk API", "status": "ok"}


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


# Routers principais
app.include_router(auth_router)
app.include_router(entities_router)
app.include_router(users_router)
app.include_router(sources_router)
app.include_router(risks_router)  # <<< CRÍTICO (ativa /risks/search, /confirm, /pdf, etc.)
app.include_router(audit_router)
app.include_router(public_router)

# Extras (só liga se tiveres estes routers no projecto)
# app.include_router(insurance_sources_router)
# app.include_router(compliance_sources_router)
