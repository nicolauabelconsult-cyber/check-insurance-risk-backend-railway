# config.py
import os

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Qwerty!080397"

# ✅ ESTA LINHA FALTAVA
DATABASE_URL = os.getenv("DATABASE_URL")  # Render define isto quando usas Postgres

CORS_ORIGINS_LIST = [
    "https://checkinsurancerisk.com",
    "https://www.checkinsurancerisk.com",
    "http://localhost:5173",
]

UPLOAD_DIR = "/tmp/uploads"
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-later")
