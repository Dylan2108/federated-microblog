"""Timeline home con fan-out en escritura; la local y la federada se consultan al leer.

Semántica: la home de un usuario contiene sus notas, las de las cuentas que sigue y lo que éstas
republican, más recientes primero (una republicación se ordena por la fecha en que se republicó).
Cada nota aparece una sola vez: si llega por varios caminos, se queda la entrada más reciente.
Al seguir a alguien se traen sus últimas BACKFILL notas; al dejar de seguirle desaparecen las suyas.

La home contiene notas de cualquier visibilidad porque sólo se reparten al autor y a sus seguidores
aceptados, que pueden verlas todas (services/privacy.py). La local y la federada sólo muestran `public`.

Estas funciones no hacen commit: lo hace el service que las llama, en la misma transacción.
"""

from app.domain.entities import Actor, Note, Repost
from app.domain.ports import Repos
from app.services import privacy

BACKFILL = 20

def _entry(owner_id: str, note_id: str, sort_date, reposted_by: str | None = None) -> dict:
    return {"owner_id": owner_id, "note_id": note_id, "sort_date": sort_date, "reposted_by": reposted_by}

async def _audience(repos: Repos, actor_id: str) -> set[str]:
    """Homes a las que llega lo que publica o republica `actor_id`: la suya y las de sus seguidores locales."""
    return {actor_id, *await repos.follows.local_follower_ids(actor_id)}

async def fan_out(repos: Repos, note: Note) -> None:
    owners = await _audience(repos, note.author_id)
    await repos.timeline.add([_entry(o, note.id, note.published) for o in owners])

async def fan_out_repost(repos: Repos, repost: Repost) -> None:
    owners = await _audience(repos, repost.actor_id)
    await repos.timeline.add([_entry(o, repost.note_id, repost.published, repost.actor_id) for o in owners])

async def remove_repost(repos: Repos, actor_id: str, note: Note) -> None:
    """Quita la republicación de las homes. Quien también recibía la nota por otro camino (el autor
    u otra republicación que sigue en pie) la recupera: se vuelve a repartir por esos caminos."""
    await repos.timeline.remove_repost(actor_id, note.id)
    await fan_out(repos, note)
    for other in await repos.reposts.of_note(note.id):
        await fan_out_repost(repos, other)

async def backfill(repos: Repos, owner: Actor, author: Actor) -> None:
    recent = await repos.notes.recent_by_author(author.id, BACKFILL)
    await repos.timeline.add([_entry(owner.id, n.id, n.published) for n in recent])

async def remove_author(repos: Repos, owner: Actor, author: Actor) -> None:
    await repos.timeline.remove_author(owner.id, author.id)

async def home(repos: Repos, owner: Actor, limit: int = 50) -> list[tuple[Note, Actor | None]]:
    """(nota, quién la republicó o None), más recientes primero."""
    return await repos.timeline.home(owner.id, limit)

async def local(repos: Repos, limit: int = 50) -> list[Note]:
    """Notas públicas de los usuarios de este servidor."""
    return await repos.notes.latest(limit, privacy.PUBLIC_TIMELINES, local_only=True)

async def federated(repos: Repos, limit: int = 50) -> list[Note]:
    """Notas públicas que este servidor conoce, de cualquier servidor."""
    return await repos.notes.latest(limit, privacy.PUBLIC_TIMELINES, local_only=False)