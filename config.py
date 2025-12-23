# config.py
import os

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Qwerty!080397"

DATABASE_URL = os.getenv("DATABASE_URL")  # Render/Postgres (opcional)

ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "12"))

CORS_ORIGINS_LIST = [
    "https://checkinsurancerisk.com",
    "https://www.checkinsurancerisk.com",
    "http://localhost:5173",
]

UPLOAD_DIR = "/tmp/uploads"
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-later")
