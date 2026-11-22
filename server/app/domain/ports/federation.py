import logging
from typing import Protocol

log = logging.getLogger(__name__)

class ServerUnavailable(Exception):
    """El servidor remoto no responde (contrato: 503)."""

class Federation(Protocol):
    """Comunicación con otros servidores, vista desde la lógica de negocio.

    `deliver` encarga entregar una actividad (un dict JSON con un `id` global) al servidor `domain`.
    No espera a que llegue: la entrega es asíncrona y eventual.
    (F1: llamada a otro actor Ray; F2: fila en `deliveries`, en la misma transacción, + HTTP).

    `fetch_actor` sí es síncrona: pregunta a `domain` por uno de sus usuarios (None si no existe).
    """

    async def deliver(self, domain: str, activity: dict) -> None: ...
    async def fetch_actor(self, domain: str, username: str) -> dict | None:
        """Lanza ServerUnavailable si `domain` no responde."""
        ...

class NoFederation:
    """Servidor aislado: no conoce a nadie. Lo usan el servidor HTTP hasta la F2 y los tests locales."""
    async def deliver(self, domain: str, activity: dict) -> None:
        log.warning("activity_dropped", extra={"activity_id": activity["id"], "to": domain})

    async def fetch_actor(self, domain: str, activity: dict) -> dict | None:
        raise ServerUnavailable(domain)