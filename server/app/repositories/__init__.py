"""Acceso a datos. Es la única capa que construye consultas SQLAlchemy.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.actors import ActorRepo

class Repos:
    """Repositorios que comparten una sesión: todo lo que hace una acción va en una transacción."""
    def __init__(self, db: AsyncSession):
        self.db = db
        self.actors = ActorRepo(self.db)

    async def commit(self) -> None:
        await self.db.commit()