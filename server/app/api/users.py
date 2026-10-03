from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user, get_repos
from app.domain.entities import Actor
from app.domain.ports import Repos
from app.schemas.client import NoteOut, UserOut
from app.services import notes, users

router = APIRouter(prefix="/api/users", tags=["users"])

async def get_user(username: str, repos: Repos) -> Actor:
    actor = await users.get_local(repos, username)
    if actor is None:
        raise HTTPException(404, "Usuario no encontrado")
    return actor

@router.get("/{username}", response_model=UserOut)
async def profile(username: str, repos: Repos = Depends(get_repos)):
    return await get_user(username, repos)

@router.get("/{username}/notes", response_model=list[NoteOut])
async def user_notes(username: str, repos: Repos = Depends(get_repos)):
    return await notes.by_author(repos, await get_user(username, repos))