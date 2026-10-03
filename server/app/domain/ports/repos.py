from typing import Protocol

from app.domain.ports.actors import ActorRepo
from app.domain.ports.notes import NoteRepo

class Repos(Protocol):
    """Repositorios de una acción; commit() confirma todo lo hecho con ellos de una vez."""
    actors: ActorRepo
    notes: NoteRepo

    async def commit(self) -> None: ...