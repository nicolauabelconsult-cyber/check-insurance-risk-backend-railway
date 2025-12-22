from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .db.session import init_db
from .routers import auth, users, sources, dashboard

app = FastAPI(title="Check Insurance Risk API", version="1.0.0")

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/")
def root():
    return {"message": "API Online — Check Insurance Risk"}

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(sources.router)
app.include_router(dashboard.router)
