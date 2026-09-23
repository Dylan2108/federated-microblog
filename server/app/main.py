from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(title="Red federada de micropublicaciones")

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "domain": settings.domain}