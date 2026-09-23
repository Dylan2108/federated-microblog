from fastapi import FastAPI
from app.core.config import settings
from app.core.db import Base, engine
from app import models

app = FastAPI(title="Red federada de micropublicaciones")

@app.on_event("startup")
async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "domain": settings.domain}