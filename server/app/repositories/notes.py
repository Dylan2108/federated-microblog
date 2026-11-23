from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Note, Tombstone
from app.repositories.tables import actors, notes

class NoteRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, note: Note) -> None:
        self.db.add(note)
        await self.db.flush()

    async def get(self, note_id: str) -> Note | None:
        return await self.db.get(Note, note_id)

    async def delete(self, note: Note) -> None:
        # Las republicaciones y las entradas de timeline se borran en cascada (tables.py).
        self.db.add(Tombstone(id=note.id, author_id=note.author_id))
        await self.db.delete(note)

    async def add_tombstone(self, tombstone: Tombstone) -> None:
        self.db.add(tombstone)

    async def get_tombstone(self, note_id: str) -> Tombstone | None:
        return await self.db.get(Tombstone, note_id)

    async def recent_by_author(self, author_id: str, limit: int, visibilities: set[str] | None = None) -> list[Note]:
        query = select(Note).where(notes.c.author_id == author_id)
        if visibilities is not None:
            query = query.where(notes.c.visibility.in_(visibilities))
        rows = await self.db.scalars(query.order_by(notes.c.published.desc()).limit(limit))
        return list(rows)

    async def latest(self, limit: int, visibilities: set[str], local_only: bool) -> list[Note]:
        query = select(Note).where(notes.c.visibility.in_(visibilities))
        if local_only:
            query = query.join(actors, actors.c.id == notes.c.author_id).where(actors.c.is_local)
        rows = await self.db.scalars(query.order_by(notes.c.published.desc()).limit(limit))
        return list(rows)