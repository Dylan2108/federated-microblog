from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user, get_repos, get_optional_user
from app.domain.entities import Actor
from app.domain.ports import Repos
from app.schemas.client import NoteOut, UserOut, FollowOut
from app.services import notes, users, follows

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
async def user_notes(
    username: str,
    limit: int = Query(50, ge=1, le=200),
    viewer: Actor | None = Depends(get_optional_user),
    repos: Repos = Depends(get_repos)
):
    return await notes.by_author(repos, await get_user(username, repos), viewer, limit)

@router.get("/{username}/followers", response_model=list[UserOut])
async def user_followers(username: str, repos: Repos = Depends(get_repos)):
    return await follows.followers(repos, await get_user(username, repos))

@router.get("/{username}/following", response_model=list[UserOut])
async def user_following(username: str, repos: Repos = Depends(get_repos)):
    return await follows.following(repos, await get_user(username, repos))

@router.post("/{username}/follow", response_model=FollowOut)
async def follow(
    username: str, user: Actor = Depends(get_current_user), repos: Repos = Depends(get_repos)
):
    try:
        return FollowOut(state=await follows.follow(repos, user, await get_user(username, repos)))
    except follows.CannotFollowSelf:
        raise HTTPException(400, "No puedes seguirte a ti mismo")

@router.delete("/{username}/follow", status_code=204)
async def unfollow(
    username: str, user: Actor = Depends(get_current_user), repos: Repos = Depends(get_repos)
):
    await follows.unfollow(repos, user, await get_user(username, repos))