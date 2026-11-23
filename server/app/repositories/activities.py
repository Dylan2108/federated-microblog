from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.entities import utcnow
from app.repositories.tables import received_activities

class ActivityRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def seen(self, activity_id: str) -> bool:
        query = select(received_activities.c.id).where(received_activities.c.id == activity_id)
        return await self.db.scalar(query) is not None

    async def add(self, activity_id: str) -> None:
        await self.db.execute(received_activities.insert().values(id=activity_id, received=utcnow()))