from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Actor

class ActorRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, actor_id: str) -> Actor | None:
        return await self.db.get(Actor, actor_id)

    def add(self, actor: Actor) -> None:
        self.db.add(actor)