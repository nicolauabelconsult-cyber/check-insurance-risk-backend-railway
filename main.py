# main.py – backend Check Insurance Risk (versão corrigida)

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from users import router as users_router
from info_sources import router as info_sources_router
from dashboard import router as dashboard_router
from auth import router as auth_router, get_password_hash
from models import User, UserRole

# ------------------------------------------------------------
# Criar tabelas automaticamente
# ------------------------------------------------------------
Base.metadata.create_all(bind=engine)

# ------------------------------------------------------------
# Inicialização da aplicação
# ------------------------------------------------------------
app = FastAPI(
    title="Check Insurance Risk API",
    version="1.0.0",
    description="Backend para o sistema de gestão e análise de risco."
)

# ------------------------------------------------------------
# CORS – permitir acesso do frontend
# ------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # podes limitar depois para o domínio do frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# ENDPOINT TEMPORÁRIO PARA CRIAÇÃO DO ADMIN
# (executa 1 vez no Render -> /create-admin-temp)
# ------------------------------------------------------------
@app.post("/create-admin-temp")
def create_admin_temp(db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        return {"message": "Admin já existe", "username": existing.username}

    admin = User(
        username="admin",
        email="admin@example.com",
        full_name="Administrador do Sistema",
        hashed_password=get_password_hash("QWE!asd!ZXC!080397"),  # PASSWORD NOVA
        role=UserRole.ADMIN.value,
        is_active=True,
    )

    db.add(admin)
    db.commit()
    db.refresh(admin)

    return {"message": "Admin criado com sucesso", "username": admin.username}


# ------------------------------------------------------------
# ROTAS DO SISTEMA (com prefixo /api)
# ------------------------------------------------------------
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(info_sources_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")


# ------------------------------------------------------------
# ROTA PRINCIPAL
# ------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "API Online — Check Insurance Risk"}

