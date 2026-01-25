from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Check Insurance Risk API"
    ENV: str = "development"
    DATABASE_URL: str

    JWT_SECRET: str
    JWT_ACCESS_MINUTES: int = 30
    JWT_REFRESH_DAYS: int = 30

    SUPERADMIN_EMAIL: str
    SUPERADMIN_PASSWORD: str
    SUPERADMIN_NAME: str = "Nicolau Abel"

    class Config:
        env_file = ".env"

settings = Settings()
