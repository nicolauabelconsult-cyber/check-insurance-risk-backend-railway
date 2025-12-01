import os
from pydantic import BaseModel
from typing import List

class Settings(BaseModel):
    PROJECT_NAME: str = "Check Insurance Risk Backend"
    API_PREFIX: str = "/api"

    # CORS – permitir Netlify + localhost
    BACKEND_CORS_ORIGINS: List[str] = [
        "*",
        "http://localhost:5173",
        "https://check-insurance-risk.netlify.app",
    ]

    # Base de dados (Render Postgres ou SQLite local)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./database.db"
    )

    # Secret JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

settings = Settings()
