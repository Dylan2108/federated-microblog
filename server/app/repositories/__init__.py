"""Acceso a datos. Es la única capa que construye consultas SQLAlchemy.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.actors import ActorRepo
from app.repositories.notes import NoteRepo
from app.repositories.follows import FollowRepo
from app.repositories.timeline import TimelineRepo

class Repos:
    """Repositorios que comparten una sesión: todo lo que hace una acción va en una transacción."""
    def __init__(self, db: AsyncSession):
        self.db = db
        self.actors = ActorRepo(db)
        self.notes = NoteRepo(db)
        self.follows = FollowRepo(db)
        self.timeline = TimelineRepo(db)

    async def commit(self) -> None:
        await self.db.commit()