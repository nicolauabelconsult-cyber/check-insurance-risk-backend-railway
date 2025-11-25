from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Check Insurance Risk Backend"
    API_PREFIX: str = "/api"

    DATABASE_URL: str = "postgresql://user:password@localhost:5432/check_insurance"

    AUTH_SECRET: str = "change-this-secret"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 12

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://teu-frontend.netlify.app",
    ]

    RISK_WEIGHTS: dict[str, int] = {
        "PEP": 95,
        "FRAUD": 90,
        "SANCTIONS": 100,
        "CLAIMS": 50,
        "INTERNAL": 40,
    }

    class Config:
        env_file = ".env"


settings = Settings()
