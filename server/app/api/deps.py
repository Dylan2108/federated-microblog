from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import read_token
from app.domain.entities import Actor
from app.repositories import Repos
from app.services import users

_bearer = HTTPBearer(auto_error=False)

async def get_repos(db: AsyncSession = Depends(get_db)) -> Repos:
    return Repos(db)

async def get_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
        repos: Repos = Depends(get_repos)
) -> Actor:
    username = read_token(credentials.credentials) if credentials else None
    actor = await users.get_local(repos, username) if username else None
    if actor is None:
        raise HTTPException(401, "Token invalido o caducado")
    return actor