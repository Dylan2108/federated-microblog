from typing import Protocol

from app.domain.ports.activities import ActivityRepo
from app.domain.ports.actors import ActorRepo
from app.domain.ports.federation import Federation
from app.domain.ports.notes import NoteRepo
from app.domain.ports.reposts import RepostRepo
from app.domain.ports.follows import FollowRepo
from app.domain.ports.timeline import TimelineRepo

class Repos(Protocol):
    """Lo que un caso de uso necesita del exterior para una acción: los repositorios, la federación y
    el dominio de este servidor. commit() confirma todo lo hecho de una vez.

    La federación va aquí porque forma parte de la misma acción: en la versión nativa, entregar una
    actividad es guardarla en la cola de salida dentro de la misma transacción.
    """
    domain: str
    federation: Federation
    actors: ActorRepo
    notes: NoteRepo
    reposts: RepostRepo
    follows: FollowRepo
    timeline: TimelineRepo
    activities: ActivityRepo

    async def commit(self) -> None: ...