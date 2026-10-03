from typing import Protocol

from app.domain.entities import Note

class NoteRepo(Protocol):
    async def add(self, note: Note) -> None: ...
    async def recent_by_author(self, author_id: str, limit: int) -> list[Note]: ...