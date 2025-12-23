# config.py
import os

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Qwerty!080397"

CORS_ORIGINS_LIST = [
    "https://checkinsurancerisk.com",
    "https://www.checkinsurancerisk.com",
    "http://localhost:5173",
]

UPLOAD_DIR = "/tmp/uploads"
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-later")
