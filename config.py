import os

APP_NAME = "Check Insurance Risk API"

# SUPER ADMIN (seed)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Qwerty!080397"

# SECURITY
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

# DATABASE
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# CORS
CORS_ORIGINS = [
    "http://localhost:5173",
    "https://checkinsurancerisk.com",
    "https://www.checkinsurancerisk.com",
]

UPLOAD_DIR = "/tmp/uploads"
