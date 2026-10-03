from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_repos
from app.domain.entities import Actor
from app.domain.ports import Repos
from app.schemas.client import NoteIn, NoteOut
from app.services import notes

router = APIRouter(prefix="/api/notes", tags=["notes"])

@router.post("", response_model=NoteOut, status_code=201)
async def create_note(
    body: NoteIn, user: Actor = Depends(get_current_user), repos: Repos = Depends(get_repos)
):
    return await notes.create(repos, user, body.content)