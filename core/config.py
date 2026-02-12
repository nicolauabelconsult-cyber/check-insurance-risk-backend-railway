from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    BASE_URL: str = "https://check-insurance-risk.com"
    PDF_SECRET_KEY: str


settings = Settings()
