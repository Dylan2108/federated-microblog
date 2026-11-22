from contextlib import contextmanager
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user, get_repos, get_optional_user
from app.domain.entities import Actor
from app.domain.ports import Repos
from app.schemas.client import NoteIn, NoteOut, NoteEditIn
from app.services import notes

router = APIRouter(prefix="/api/notes", tags=["notes"])

NoteId = Query(description="Id global de la nota (URL)")

_ERRORS = {
    notes.NoteNotFound: (404, "Nota no encontrada"),
    notes.NotAuthor: (403, "Solo el autor puede modificar la nota"),
    notes.NotRepostable: (403, "Las notas solo para seguidores no se pueden republicar")
}

@contextmanager
def _http_errors():
    try:
        yield
    except tuple(_ERRORS) as exc:
        status, detail = _ERRORS[type(exc)]
        raise HTTPException(status, detail)
    
@router.post("", response_model=NoteOut, status_code=201)
async def create_note(
    body: NoteIn, user: Actor = Depends(get_current_user), repos: Repos = Depends(get_repos)
):
    return await notes.create(repos, user, body.content, body.visibility)

@router.get("", response_model=NoteOut)
async def get_note(
    id: str = NoteId,
    viewer: Actor | None = Depends(get_optional_user),
    repos: Repos = Depends(get_repos)
):
    note = await notes.get_visible(repos, id, viewer)
    if note is None:
        raise HTTPException(404, "Nota no encontrada")
    return note

@router.patch("", response_model=NoteOut)
async def edit_note(
    body: NoteEditIn,
    id: str = NoteId,
    user: Actor = Depends(get_current_user),
    repos: Repos = Depends(get_repos),
):
    with _http_errors():
        return await notes.edit(repos, user, id, body.content)

@router.delete("", status_code=204)
async def delete_note(
    id: str = NoteId, user: Actor = Depends(get_current_user), repos: Repos = Depends(get_repos)
):
    with _http_errors():
        await notes.delete(repos, user, id)

@router.post("/repost", status_code=204)
async def repost(
    id: str = NoteId, user: Actor = Depends(get_current_user), repos: Repos = Depends(get_repos)
):
    with _http_errors():
        await notes.repost(repos, user, id)

@router.delete("/repost", status_code=204)
async def unrepost(
    id: str = NoteId, user: Actor = Depends(get_current_user), repos: Repos = Depends(get_repos)
):
    with _http_errors():
        await notes.unrepost(repos, user, id)