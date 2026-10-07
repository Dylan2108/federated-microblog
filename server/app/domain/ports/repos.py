from typing import Protocol

from app.domain.ports.actors import ActorRepo
from app.domain.ports.notes import NoteRepo
from app.domain.ports.follows import FollowRepo

class Repos(Protocol):
    """Repositorios de una acción; commit() confirma todo lo hecho con ellos de una vez."""
    actors: ActorRepo
    notes: NoteRepo
    follows: FollowRepo

    async def commit(self) -> None: ...