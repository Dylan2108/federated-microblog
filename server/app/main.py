from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api import auth, notes, users
from app.core.config import settings
from app.core.db import engine
from app.repositories.tables import metadata

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield

app = FastAPI(title="Red federada de micropublicaciones", lifespan=lifespan)
for module in (auth, users, notes):
    app.include_router(module.router)

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "domain": settings.domain}