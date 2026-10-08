from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Note
from app.repositories.tables import notes, timeline_entries

class TimelineRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, entries: list[dict]) -> None:
        """Entradas {owner_id, note_id, sort_date}. Las ya existentes se ignoran (idempotente)."""
        if entries:
            await self.db.execute(insert(timeline_entries).values(entries).on_conflict_do_nothing())

    async def remove_author(self, owner_id: str, author_id: str) -> None:
        await self.db.execute(
            delete(timeline_entries).where(
                timeline_entries.c.owner_id == owner_id,
                timeline_entries.c.note_id.in_(select(notes.c.id).where(notes.c.author_id == author_id)),
            )
        )

    async def home(self, owner_id: str, limit: int) -> list[Note]:
        rows = await self.db.scalars(
            select(Note)
            .join(timeline_entries, timeline_entries.c.note_id == notes.c.id)
            .where(timeline_entries.c.owner_id == owner_id)
            .order_by(timeline_entries.c.sort_date.desc())
            .limit(limit)
        )
        return list(rows)