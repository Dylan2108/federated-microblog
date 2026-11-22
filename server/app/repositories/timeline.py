from sqlalchemy import delete, select, and_, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.entities import Actor, Note
from app.repositories.tables import notes, timeline_entries

entries_t = timeline_entries.c

class TimelineRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, entries: list[dict]) -> None:
        if not entries:
            return
        stmt = insert(timeline_entries).values(entries)
        await self.db.execute(
            stmt.on_conflict_do_update(
                index_elements=[entries_t.owner_id, entries_t.note_id],
                set_={"sort_date": stmt.excluded.sort_date, "reposted_by": stmt.excluded.reposted_by},
                where=entries_t.sort_date < stmt.excluded.sort_date,
            )
        )

    async def remove_author(self, owner_id: str, author_id: str) -> None:
        by_author = select(notes.c.id).where(notes.c.author_id == author_id)
        await self.db.execute(
            delete(timeline_entries).where(
                entries_t.owner_id == owner_id,
                or_(
                    entries_t.reposted_by == author_id,
                    and_(entries_t.reposted_by.is_(None), entries_t.note_id.in_(by_author)),
                ),
            )
        )

    async def remove_repost(self, actor_id: str, note_id: str) -> None:
        await self.db.execute(
            delete(timeline_entries).where(entries_t.note_id == note_id, entries_t.reposted_by == actor_id)
        )

    async def home(self, owner_id: str, limit: int) -> list[tuple[Note, Actor | None]]:
        reposter = aliased(Actor)
        rows = await self.db.execute(
            select(Note, reposter)
            .join(timeline_entries, entries_t.note_id == notes.c.id)
            .outerjoin(reposter, reposter.id == entries_t.reposted_by)
            .where(entries_t.owner_id == owner_id)
            .order_by(entries_t.sort_date.desc())
            .limit(limit)
        )
        return [(note, by) for note, by in rows]