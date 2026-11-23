"""Un servidor de la red con el estado en memoria. No usa Ray: es lo que ejecuta cada actor.

Reutiliza la aplicación HTTP de `server/` (los mismos routers y casos de uso), cambiando sólo el
adaptador de persistencia: `MemoryRepos` en lugar de PostgreSQL. Así el prototipo cumple el contrato
por construcción y no duplica ningún endpoint.
"""

import httpx
from app.api.deps import get_repos
from app.domain.ports import Federation
from app.main import create_app
from app.repositories.memory import MemoryRepos


class InMemoryServer:
    def __init__(self, domain: str, federation: Federation | None = None):
        self.repos = MemoryRepos(domain, federation)  # todo el estado del servidor
        app = create_app()
        app.dependency_overrides[get_repos] = lambda: self.repos
        # Cliente que entrega las peticiones a la aplicación dentro del proceso, sin red.
        self._http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=f"http://{domain}")

    async def handle(self, method: str, url: str, headers: dict, body: bytes) -> tuple[int, dict, bytes]:
        """Atiende una petición HTTP del contrato: (estado, cabeceras, cuerpo)."""
        response = await self._http.request(method, url, headers=headers, content=body)
        return response.status_code, dict(response.headers), response.content
