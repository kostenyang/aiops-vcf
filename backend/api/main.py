from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from api.routers import alerts, changes, reports, troubleshoot, capacity

class Settings(BaseSettings):
    cors_origins: str = "http://localhost:5173"
    class Config:
        env_file = ".env"

settings = Settings()
app = FastAPI(title="AIOps for VCF", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(alerts.router,      prefix="/api/alerts",      tags=["alerts"])
app.include_router(changes.router,     prefix="/api/changes",     tags=["changes"])
app.include_router(reports.router,     prefix="/api/reports",     tags=["reports"])
app.include_router(troubleshoot.router,prefix="/api/troubleshoot",tags=["troubleshoot"])
app.include_router(capacity.router,    prefix="/api/capacity",    tags=["capacity"])

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
