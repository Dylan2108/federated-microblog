from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities import Repost
from app.repositories.tables import reposts

class RepostRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def exists(self, actor_id: str, note_id: str) -> bool:
        return await self.db.get(Repost, (actor_id, note_id)) is not None

    def add(self, repost: Repost) -> None:
        self.db.add(repost)

    async def remove(self, actor_id: str, note_id: str) -> None:
        await self.db.execute(
            delete(reposts).where(reposts.c.actor_id == actor_id, reposts.c.note_id == note_id)
        )

    async def of_note(self, note_id: str) -> list[Repost]:
        return list(await self.db.scalars(select(Repost).where(reposts.c.note_id == note_id)))