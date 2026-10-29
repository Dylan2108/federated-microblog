import logging
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

from app.api import auth, notes, users, timelines
from app.core.config import settings
from app.core.db import engine
from app.core.log import request_id, setup_logging
from app.repositories.tables import metadata

setup_logging()
log = logging.getLogger("app.http")

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    log.info("server_started", extra={"domain": settings.domain})
    yield

app = FastAPI(title="Red federada de micropublicaciones", lifespan=lifespan)
for module in (auth, users, notes, timelines):
    app.include_router(module.router)

@app.middleware("http")
async def request_context(request: Request, call_next):
    """Asigna un request_id a cada petición (o reutiliza el del cliente) y registra una línea por petición."""
    rid = request.headers.get("X-Request-ID", "")[:64] or uuid.uuid4().hex[:12]
    token = request_id.set(rid)
    start = time.perf_counter()
    info = {"method": request.method, "path": request.url.path}
    try:
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request_failed", extra={**info, "duration_ms": _ms_since(start)})
            raise
        response.headers["X-Request-ID"] = rid
        log.info("request", extra={**info, "status": response.status_code, "duration_ms": _ms_since(start)})
        return response
    finally:
        request_id.reset(token)

def _ms_since(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "domain": settings.domain}