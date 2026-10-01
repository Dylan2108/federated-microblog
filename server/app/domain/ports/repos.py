from typing import Protocol

from app.domain.ports.actors import ActorRepo

class Repos(Protocol):
    """Repositorios de una acción; commit() confirma todo lo hecho con ellos de una vez."""
    actors: ActorRepo

    async def commit(self) -> None: ...