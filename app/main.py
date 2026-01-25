from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .settings import settings
from .routers import auth, entities, users

app = FastAPI(title=settings.APP_NAME, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://checkinsurancerisk.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(entities.router)
app.include_router(users.router)

@app.get("/health")
def health():
    return {"status": "ok"}
