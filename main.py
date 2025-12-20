from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from users import router as users_router
from info_sources import router as info_sources_router
from dashboard import router as dashboard_router
from auth import router as auth_router  # ✅ ADICIONADO

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Check Insurance Risk API",
    version="1.0.0",
    description="Backend para o sistema de gestão e análise de risco."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prefixo /api
app.include_router(auth_router, prefix="/api")           # ✅ LOGIN FUNCIONA
app.include_router(users_router, prefix="/api")
app.include_router(info_sources_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "API Online — Check Insurance Risk"}
