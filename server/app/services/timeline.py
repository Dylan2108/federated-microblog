"""Timeline home con fan-out en escritura.

Semántica: la home de un usuario contiene sus notas y las de las cuentas que sigue,
ordenadas por fecha de publicación (más recientes primero). Al seguir a alguien se
traen sus últimas BACKFILL notas; al dejar de seguirle desaparecen todas las suyas.

Estas funciones no hacen commit: lo hace el service que las llama, en la misma transacción.
"""

from app.domain.entities import Actor, Note
from app.domain.ports import Repos

BACKFILL = 20

def entries(owner_ids, notes: list[Note]) -> list[dict]:
    return [{"owner_id": o, "note_id": n.id, "sort_date": n.published} for o in owner_ids for n in notes]

async def fan_out(repos: Repos, note: Note) -> None:
    """Coloca la nota en la home de su autor y de cada seguidor local."""
    owners = {note.author_id, *await repos.follows.local_follower_ids(note.author_id)}
    await repos.timeline.add(entries(owners, [note]))

async def backfill(repos: Repos, owner: Actor, author: Actor) -> None:
    recent = await repos.notes.recent_by_author(author.id, BACKFILL)
    await repos.timeline.add(entries([owner.id], recent))

async def remove_author(repos: Repos, owner: Actor, author: Actor) -> None:
    await repos.timeline.remove_author(owner.id, author.id)

async def home(repos: Repos, owner: Actor, limit: int = 50) -> list[Note]:
    return await repos.timeline.home(owner.id, limit)