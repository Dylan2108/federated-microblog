from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user, get_repos, get_optional_user
from app.domain.entities import Actor
from app.domain.ports import Repos, ServerUnavailable
from app.schemas.client import NoteOut, UserOut, FollowOut
from app.services import notes, users, follows

router = APIRouter(prefix="/api/users", tags=["users"])

async def _get_user(handle: str, repos: Repos) -> Actor:
    """Usuario local o remoto (`ana`, `ana@server-b`, `@ana@server-b`)."""
    try:
        actor = await users.find(repos, handle)
    except ServerUnavailable:
        raise HTTPException(503, "Su servidor no responde")
    if actor is None:
        raise HTTPException(404, "Usuario no encontrado")
    return actor

async def _get_local_user(handle: str, repos: Repos) -> Actor:
    """followers y following sólo existen para usuarios de este servidor.""" 
    actor = await users.find(repos, handle, fetch=False)
    if actor is None or not actor.is_local:
        raise HTTPException(404, "Usuario no encontrado")
    return actor

@router.get("/{handle}", response_model=UserOut)
async def profile(handle: str, repos: Repos = Depends(get_repos)):
    return await _get_user(handle, repos)

@router.get("/{handle}/notes", response_model=list[NoteOut])
async def user_notes(
    handle: str,
    limit: int = Query(50, ge=1, le=200),
    viewer: Actor | None = Depends(get_optional_user),
    repos: Repos = Depends(get_repos)
):
    """De un usuario remoto, las notas suyas que este servidor ha recibido."""
    return await notes.by_author(repos, await _get_user(handle, repos), viewer, limit)

@router.get("/{handle}/followers", response_model=list[UserOut])
async def user_followers(handle: str, repos: Repos = Depends(get_repos)):
    return await follows.followers(repos, await _get_local_user(handle, repos))

@router.get("/{handle}/following", response_model=list[UserOut])
async def user_following(handle: str, repos: Repos = Depends(get_repos)):
    return await follows.following(repos, await _get_local_user(handle, repos))

@router.post("/{handle}/follow", response_model=FollowOut)
async def follow(
    handle: str, user: Actor = Depends(get_current_user), repos: Repos = Depends(get_repos)
):
    try:
        return FollowOut(state=await follows.follow(repos, user, await _get_user(handle, repos)))
    except follows.CannotFollowSelf:
        raise HTTPException(400, "No puedes seguirte a ti mismo")

@router.delete("/{handle}/follow", status_code=204)
async def unfollow(
    handle: str, user: Actor = Depends(get_current_user), repos: Repos = Depends(get_repos)
):
    await follows.unfollow(repos, user, await _get_user(handle, repos))