import os

APP_NAME = "Check Insurance Risk API"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Qwerty!080397"

SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PROD")
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

UPLOAD_DIR = "/tmp/uploads"

CORS_ORIGINS = [
    "https://checkinsurancerisk.com",
    "https://www.checkinsurancerisk.com",
    "http://localhost:5173",
]
