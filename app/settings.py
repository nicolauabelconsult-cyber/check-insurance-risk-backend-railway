from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Check Insurance Risk API"

    DATABASE_URL: str

    JWT_SECRET: str
    JWT_ACCESS_MINUTES: int = 60 * 6      # 6h
    JWT_REFRESH_DAYS: int = 15

    SUPERADMIN_NAME: str = "Nicolau Abel"
    SUPERADMIN_EMAIL: str
    SUPERADMIN_PASSWORD: str

    CORS_ORIGINS: str = "http://localhost:5173,https://checkinsurancerisk.com,https://www.checkinsurancerisk.com"

    def cors_list(self) -> list[str]:
        return [x.strip() for x in self.CORS_ORIGINS.split(",") if x.strip()]

settings = Settings()
