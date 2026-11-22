from typing import Protocol

from app.domain.entities import Note, Actor

class TimelineRepo(Protocol):
    async def add(self, entries: list[dict]) -> None:
        """Entradas {owner_id, note_id, sort_date, reposted_by}. Una nota está una sola vez en cada home:
        si ya estaba, sólo se sustituye por la entrada nueva cuando ésta es más reciente (idempotente)."""
        ...
    async def remove_author(self, owner_id: str, author_id:str) -> None:
        """Quita de la home las notas del autor que no llegaron por republicación y las que él republicó."""
        ...
    async def remove_repost(self, actor_id: str, note_id: str) -> None:
        """Quita de todas las homes las entradas de esa nota que llegaron por la republicación de `actor_id`."""
        ...
    async def home(self, owner_id: str, limit: int) -> list[tuple[Note, Actor | None]]:
        """(nota, quién la republicó o None), por `sort_date`, más recientes primero."""
        ...