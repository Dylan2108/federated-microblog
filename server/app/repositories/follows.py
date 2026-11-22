from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Actor, Follow, ACCEPTED, PENDING
from app.repositories.tables import actors, follows

class FollowRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, follower_id: str, followed_id: str) -> Follow | None:
        return await self.db.get(Follow, (follower_id, followed_id))

    def add(self, follow: Follow) -> None:
        self.db.add(follow)

    async def is_follower(self, follower_id: str, followed_id: str) -> bool:
        follow = await self.get(follower_id, followed_id)
        return follow is not None and follow.state == ACCEPTED

    async def remove(self, follower_id: str, followed_id: str) -> None:
        await self.db.execute(
            delete(follows).where(follows.c.follower_id == follower_id, follows.c.followed_id == followed_id)
        )

    async def followers(self, actor_id: str) -> list[Actor]:
        return await self._followers_in_state(actor_id, ACCEPTED)

    async def requests(self, actor_id: str) -> list[Actor]:
        return await self._followers_in_state(actor_id, PENDING)
    
    async def _followers_in_state(self, actor_id: str, state: str) -> list[Actor]:
        rows = await self.db.scalars(
            select(Actor)
            .join(follows, follows.c.follower_id == actors.c.id)
            .where(follows.c.followed_id == actor_id, follows.c.state == state)
            .order_by(follows.c.created_at.desc())
        )
        return list(rows)

    async def following(self, actor_id: str) -> list[Actor]:
        rows = await self.db.scalars(
            select(Actor)
            .join(follows, follows.c.followed_id == actors.c.id)
            .where(follows.c.follower_id == actor_id, follows.c.state == "accepted")
        )
        return list(rows)

    async def local_follower_ids(self, actor_id: str) -> list[str]:
        rows = await self.db.scalars(
            select(follows.c.follower_id)
            .join(actors, actors.c.id == follows.c.follower_id)
            .where(follows.c.followed_id == actor_id, follows.c.state == ACCEPTED, actors.c.is_local)
        )
        return list(rows)