from typing import List, Optional
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
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///./app.db"  # ajusta se usares Postgres

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    # O main.py está a usar settings.BACKEND_CORS_ORIGINS
    # Por isso este campo TEM de existir.
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # Opcional: se quiseres um nome alternativo na .env, por exemplo:
    # BACKEND_CORS_ORIGINS=["http://localhost:5173","https://teu-front.netlify.app"]
    # ou BACKEND_CORS_ORIGINS="http://localhost:5173,https://teu-front.netlify.app"

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

    class Settings(BaseSettings):
    # ...

    # BASE DE DADOS
    DATABASE_URL: str = "sqlite:///./app.db"          # 👈 NOVO
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///./app.db"

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
