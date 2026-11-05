import logging
import uuid

from app.core.config import settings
from app.domain.entities import Actor, Note, VISIBILITIES
from app.domain.ports import Repos
from app.services import timeline, privacy

log = logging.getLogger(__name__)

class InvalidVisibility(ValueError):
    pass

async def create(repos: Repos, author: Actor, content: str, visibility: str = "public") -> Note:
    if visibility not in VISIBILITIES:
        raise InvalidVisibility(visibility)
    note = Note(
        id=f"{settings.base_url}/notes/{uuid.uuid4()}",
        author=author,
        author_id=author.id,
        content=content,
        visibility=visibility
    )
    await repos.notes.add(note)
    await timeline.fan_out(repos, note)
    await repos.commit()
    log.info("note_created", extra={"note_id": note.id, "author_id": author.id})
    return note

async def by_author(repos: Repos, author: Actor, viewer: Actor, limit: int = 50) -> list[Note]:
    """Perfil: las notas de `author` que `viewer` (None = anónimo) puede ver."""
    visible = await privacy.visibilties_for(repos, viewer, author.id)
    return await repos.notes.recent_by_author(author.id, limit, visible)

async def get_visible(repos: Repos, note_id: str, viewer: Actor | None) -> Note | None:
    """La nota si existe y `viewer` puede verla; si no, None (no se distingue un caso del otro)."""
    note = await repos.notes.get(note_id)
    if note is None or not await privacy.can_see(repos, viewer, note):
        return None
    return note