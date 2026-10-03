from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Note
from app.repositories.tables import notes

class NoteRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, note: Note) -> None:
        self.db.add(note)
        await self.db.flush()

    async def recent_by_author(self, author_id: str, limit: int) -> list[Note]:
        rows = await self.db.scalars(
            select(Note).where(notes.c.author_id == author_id).order_by(notes.c.published.desc()).limit(limit)
        )
        return list(rows)