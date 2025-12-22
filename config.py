from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SECRET_KEY: str = "dev-secret-change-me"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 12

    DATABASE_URL: str | None = None

    CORS_ORIGINS: str = (
        "https://checkinsurancerisk.com,"
        "https://www.checkinsurancerisk.com,"
        "http://localhost:5173,"
        "http://localhost:3000"
    )

    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "Admin@12345"  # muda no Render env

    UPLOAD_DIR: str = "/tmp/cir_uploads"

settings = Settings()
