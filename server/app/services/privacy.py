"""Quién puede ver cada nota. Toda decisión de visibilidad pasa por aquí (contrato §6).

- `public` y `unlisted`: cualquiera, con o sin sesión.
- `followers`: sólo el autor y sus seguidores aceptados.
- Timelines local y federada: sólo `public`.
- Republicar: sólo `public` y `unlisted` (republicar una nota `followers` la enseñaría a quien no debe).
"""

from app.domain.entities import FOLLOWERS, PUBLIC, UNLISTED, Actor, Note
from app.domain.ports import Repos

PUBLIC_TIMELINES = {PUBLIC}
REPOSTABLE = {PUBLIC, UNLISTED}

async def visibilties_for(repos: Repos, viewer: Actor | None, author_id: str) -> set[str]:
    """Visibilidades de las notas de `author_id` que `viewer` (None = anónimo) puede ver."""
    if viewer is not None and (
        viewer.id == author_id or await repos.follows.is_follower(viewer.id, author_id)
    ):
        return {PUBLIC, UNLISTED, FOLLOWERS}
    return {PUBLIC, UNLISTED}

async def can_see(repos: Repos, viewer: Actor | None, note: Note) -> bool:
    return note.visibility in await visibilties_for(repos, viewer, note.author_id)

def can_repost(note: Note) -> bool:
    return note.visibility in REPOSTABLE