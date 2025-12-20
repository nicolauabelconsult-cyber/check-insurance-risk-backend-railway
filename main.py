from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from users import router as users_router
from info_sources import router as info_sources_router
from dashboard import router as dashboard_router
from risk_engine import router as risk_router
from reporting import router as reporting_router

# Criar tabelas (caso não existam)
Base.metadata.create_all(bind=engine)


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
    allow_origins=["*"],  # podes restringir depois
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# Prefixo /api — compatível com o frontend
# ------------------------------------------------------------

app.include_router(users_router, prefix="/api")
app.include_router(info_sources_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(risk_router, prefix="/api")
app.include_router(reporting_router, prefix="/api")


# ------------------------------------------------------------
# Rota raiz
# ------------------------------------------------------------

@app.get("/")
def root():
    return {"message": "API Online — Check Insurance Risk"}


