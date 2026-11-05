from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user, get_repos, get_optional_user
from app.domain.entities import Actor
from app.domain.ports import Repos
from app.schemas.client import NoteIn, NoteOut
from app.services import notes

router = APIRouter(prefix="/api/notes", tags=["notes"])

@router.post("", response_model=NoteOut, status_code=201)
async def create_note(
    body: NoteIn, user: Actor = Depends(get_current_user), repos: Repos = Depends(get_repos)
):
    return await notes.create(repos, user, body.content, body.visibility)

@router.get("", response_model=NoteOut)
async def get_note(
    id: str = Query(description="Id global de la nota (URL)"),
    viewer: Actor | None = Depends(get_optional_user),
    repos: Repos = Depends(get_repos)
):
    note = await notes.get_visible(repos, id, viewer)
    if note is None:
        raise HTTPException(404, "Nota no encontrada")
    return note