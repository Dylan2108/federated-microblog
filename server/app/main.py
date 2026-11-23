import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from sqlalchemy.exc import DBAPIError

from app.api import auth, notes, users, timelines, me
from app.api.deps import get_repos
from app.core.config import settings
from app.core.db import engine
from app.core.log import request_id, setup_logging
from app.domain.ports import Repos
from app.repositories.tables import metadata

setup_logging()
log = logging.getLogger("app.http")

DB_ATTEMPTS = 30

async def create_tables() -> None:
    """Crea las tablas esperando a que la base de datos acepte conexiones.

    Nada garantiza que PostgreSQL esté listo cuando arranca este servidor (se lanzan por separado con
    `docker run`, o se reinicia uno de los dos), así que se reintenta en lugar de caerse.
    """
    for attempt in range(1, DB_ATTEMPTS + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(metadata.create_all)
            return
        except (OSError, DBAPIError) as exc:  # DNS, conexión rechazada, "the database system is starting up"
            if attempt == DB_ATTEMPTS:
                raise
            log.warning("database_unavailable", extra={"attempt": attempt, "error": type(exc).__name__})
            await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    log.info("server_started", extra={"domain": settings.domain})
    yield

def create_app(lifespan=None) -> FastAPI:
    """La aplicación HTTP del contrato. Es una función para que el prototipo Ray pueda crear la suya
    (mismos routers, repositorios en memoria) sin la base de datos de este módulo."""
    app = FastAPI(title="Red federada de micropublicaciones")
    for module in (auth, me, users, notes, timelines):
        app.include_router(module.router)
    app.middleware("http")(request_context)
    app.get("/health")(health)
    return app

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

async def health(repos: Repos = Depends(get_repos)) -> dict:
    return {"status": "ok", "domain": repos.domain}