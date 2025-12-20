from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from users import router as users_router
from info_sources import router as info_sources_router
from dashboard import router as dashboard_router
from auth import router as auth_router
from models import User, UserRole
from auth import get_password_hash

# Criar tabelas
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Check Insurance Risk API",
    version="1.0.0",
    description="Backend para o sistema de gestão e análise de risco."
)

# ------------------------------------------------------------
# CORS
# ------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # podes restringir mais tarde
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# ENDPOINT TEMPORÁRIO PARA CRIAR ADMIN
# ------------------------------------------------------------
@app.post("/create-admin-temp")
def create_admin_temp(db: Session = Depends(get_db)):
    # Verificar se já existe
    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        return {"message": "Admin já existe", "username": existing.username}

    admin = User(
        username="admin",
        email="admin@example.com",
        full_name="Administrador",
        hashed_password=get_password_hash("admin123"),
        role=UserRole.ADMIN.value,
        is_active=True,
    )

    db.add(admin)
    db.commit()

    return {"message": "Admin criado com sucesso", "username": admin.username}


# ------------------------------------------------------------
# Prefixo /api – compatível com o frontend
# ------------------------------------------------------------
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(info_sources_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")


# ------------------------------------------------------------
# Root
# ------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "API Online — Check Insurance Risk"}
