from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_user, get_repos
from app.domain.entities import Actor
from app.domain.ports import Repos
from app.schemas.client import ProfileIn, UserOut
from app.services import follows, users

router = APIRouter(prefix="/api/me", tags=["me"])

@router.get("", response_model=UserOut)
async def me(user: Actor = Depends(get_current_user)):
    return user

@router.patch("", response_model=UserOut)
async def update_me(
    body: ProfileIn, user: Actor = Depends(get_current_user), repos: Repos = Depends(get_repos)
):
    return await users.update_profile(repos, user, body.display_name, body.locked)

@router.get("/follow-requests", response_model=list[UserOut])
async def follow_requests(user: Actor = Depends(get_current_user), repos: Repos = Depends(get_repos)):
    return await follows.requests(repos, user)

async def _requester(handle: str, repos: Repos) -> Actor:
    actor = await users.find(repos, handle)
    if actor is None:
        raise HTTPException(404, "Usuario no encontrado")
    return actor

@router.post("/follow-requests/{handle}/accept", status_code=204)
async def accept(handle: str, user: Actor = Depends(get_current_user), repos: Repos = Depends(get_repos)):
    try:
        await follows.accept(repos, user, await _requester(handle, repos))
    except follows.NoFollowRequest:
        raise HTTPException(404, "No hay solicitud de ese usuario")

@router.post("/follow-requests/{handle}/reject", status_code=204)
async def reject(handle: str, user: Actor = Depends(get_current_user), repos: Repos = Depends(get_repos)):
    await follows.reject(repos, user, await _requester(handle, repos))
