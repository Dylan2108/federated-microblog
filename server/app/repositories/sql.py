"""Adaptador SQL: los repositorios de una petición sobre una misma sesión de SQLAlchemy."""
from app.domain.ports import Federation
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.activities import ActivityRepo
from app.repositories.actors import ActorRepo
from app.repositories.follows import FollowRepo
from app.repositories.notes import NoteRepo
from app.repositories.reposts import RepostRepo
from app.repositories.timeline import TimelineRepo

class SqlRepos:
    """Repositorios que comparten una sesión: todo lo que hace una acción va en una transacción."""
    def __init__(self, db: AsyncSession, domain: str, federation: Federation):
        self.db = db
        self.domain = domain
        self.federation = federation
        self.actors = ActorRepo(db)
        self.notes = NoteRepo(db)
        self.reposts = RepostRepo(db)
        self.follows = FollowRepo(db)
        self.timeline = TimelineRepo(db)
        self.activities = ActivityRepo(db)

    async def commit(self) -> None:
        await self.db.commit()