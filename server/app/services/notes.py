import uuid

from app.core.config import settings
from app.domain.entities import Actor, Note
from app.domain.ports import Repos
from app.services import timeline

async def create(repos: Repos, author: Actor, content: str) -> Note:
    note = Note(
        id=f"{settings.base_url}/notes/{uuid.uuid4()}",
        author=author,
        author_id=author.id,
        content=content,
    )
    await repos.notes.add(note)
    await timeline.fan_out(repos, note)
    await repos.commit()
    return note

async def by_author(repos: Repos, author: Actor, limit: int = 20) -> list[Note]:
    return await repos.notes.recent_by_author(author.id, limit)