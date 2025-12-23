import os

def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v if v is not None else default

SECRET_KEY = _env("SECRET_KEY", "dev-secret-change-me")
ACCESS_TOKEN_EXPIRE_HOURS = int(_env("ACCESS_TOKEN_EXPIRE_HOURS", "12"))

DATABASE_URL = os.getenv("DATABASE_URL")  # Render supplies when using Postgres

CORS_ORIGINS = _env(
    "CORS_ORIGINS",
    "https://checkinsurancerisk.com,https://www.checkinsurancerisk.com,http://localhost:5173"
)
CORS_ORIGINS_LIST = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]

ADMIN_USERNAME = _env("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = _env("ADMIN_PASSWORD", "Admin@12345")

UPLOAD_DIR = _env("UPLOAD_DIR", "/tmp/cir_uploads")
