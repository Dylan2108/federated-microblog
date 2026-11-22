from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_repos
from app.domain.entities import Actor
from app.domain.ports import Repos
from app.schemas.client import NoteOut, UserOut
from app.services import timeline

router = APIRouter(prefix="/api/timelines", tags=["timelines"])

@router.get("/home", response_model=list[NoteOut])
async def home(
    limit: int = Query(50, ge=1, le=200),
    user: Actor = Depends(get_current_user),
    repos: Repos = Depends(get_repos),
):
    return [ NoteOut.model_validate(note).model_copy(
        update={"reposted_by": UserOut.model_validate(by) if by else None}
    )
        for note, by in await timeline.home(repos, user, limit)
    ]

@router.get("/local", response_model=list[NoteOut])
async def local(limit: int = Query(50, ge=1, le=200), repos: Repos = Depends(get_repos)):
    return await timeline.local(repos, limit)

@router.get("/federated", response_model=list[NoteOut])
async def federated(limit: int = Query(50, ge=1, le=200), repos: Repos = Depends(get_repos)):
    return await timeline.federated(repos, limit)