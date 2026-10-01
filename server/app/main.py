from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api import auth
from app.core.config import settings
from app.core.db import engine
from app.repositories.tables import metadata

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield

app = FastAPI(title="Red federada de micropublicaciones", lifespan=lifespan)
app.include_router(auth.router)

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "domain": settings.domain}