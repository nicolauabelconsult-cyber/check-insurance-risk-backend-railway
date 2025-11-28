from typing import List
import json

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # INFO BÁSICA DA APLICAÇÃO
    # ------------------------------------------------------------------
    PROJECT_NAME: str = "Check Insurance Risk Backend"
    API_PREFIX: str = "/api"

    # ------------------------------------------------------------------
    # BASE DE DADOS
    # ------------------------------------------------------------------
    # Usado pelo main.py (DATABASE_URL) e por alguns setups antigos
    DATABASE_URL: str = "sqlite:///./app.db"
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///./app.db"  # se quiseres, podes usar só um

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    # O main.py está a usar settings.BACKEND_CORS_ORIGINS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # ------------------------------------------------------------------
    # AUTENTICAÇÃO / JWT
    # ------------------------------------------------------------------
    JWT_SECRET_KEY: str = "change-me"     # ideal: ler de variável de ambiente
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

    # ------------------------------------------------------------------
    # CONFIG GERAL DO Pydantic Settings (v2)
    # ------------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignora variáveis extra na .env sem rebentar
    )

    # ------------------------------------------------------------------
    # Normalizar lista de CORS vinda da .env (string -> lista)
    # ------------------------------------------------------------------
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            # Se vier como JSON (ex: '["http://localhost:5173"]')
            if v.startswith("["):
                return json.loads(v)
            # Se vier como string separada por vírgulas
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()
