"""Seguir y dejar de seguir, y solicitudes a cuentas privadas.

Un seguimiento a una cuenta privada (`locked`) queda `pending` hasta que el seguido lo acepta. Sólo uno
`accepted` cuenta como seguidor: llena la home (backfill y fan-out) y da acceso a las notas `followers`.
"""

import logging
from app.domain.entities import Actor, Follow, ACCEPTED, PENDING
from app.domain.ports import Repos
from app.services import timeline

log = logging.getLogger(__name__)

class CannotFollowSelf(Exception):
    pass

class NoFollowRequest(Exception):
    pass

async def follow(repos: Repos, follower: Actor, followed: Actor) -> str:
    """Devuelve el estado del seguimiento. Idempotente: seguir otra vez devuelve el estado que ya tenía."""
    if follower.id == followed.id:
        raise CannotFollowSelf()
    existing = await repos.follows.get(follower.id, followed.id)
    if existing is not None:
        return existing.state
    state = PENDING if followed.locked else ACCEPTED
    repos.follows.add(Follow(follower_id=follower.id, followed_id=followed.id, state=state))
    if state == ACCEPTED:
        await timeline.backfill(repos, follower, followed)
    await repos.commit()
    log.info("follow_created", extra={"follower_id": follower.id, "followed_id": followed.id})
    return state

async def unfollow(repos: Repos, follower: Actor, followed: Actor) -> None:
    """También cancela una solicitud pendiente."""
    await repos.follows.remove(follower.id, followed.id)
    await timeline.remove_author(repos, follower, followed)
    await repos.commit()
    log.info("follow_removed", extra={"follower_id": follower.id, "followed_id": followed.id})

async def followers(repos: Repos, actor: Actor) -> list[Actor]:
    return await repos.follows.followers(actor.id)

async def following(repos: Repos, actor: Actor) -> list[Actor]:
    return await repos.follows.following(actor.id)

async def requests(repos: Repos, actor: Actor) -> list[Actor]:
    return await repos.follows.requests(actor.id)

async def _accept(repos: Repos, follow: Follow, follower: Actor, followed: Actor) -> None:
    """Sin commit: lo hace quien la llama."""
    follow.state = ACCEPTED
    if follower.is_local:
        await timeline.backfill(repos, follower, followed)
    log.info("follow_accepted", extra={"follower_id": follower.id, "followed_id": followed.id})

async def accept(repos: Repos, followed: Actor, follower: Actor) -> None:
    """Idempotente: aceptar a quien ya es seguidor no hace nada. Sin solicitud ni seguimiento: NoFollowRequest."""
    follow = await repos.follows.get(follower.id, followed.id)
    if follow is None:
        raise NoFollowRequest()
    if follow.state == PENDING:
        await _accept(repos, follow, follower, followed)
        await repos.commit()

async def reject(repos: Repos, followed: Actor, follower: Actor) -> None:
    """Idempotente: rechazar sin solicitud pendiente (p. ej. por segunda vez) no hace nada.
    No sirve para echar a un seguidor ya aceptado."""
    follow = await repos.follows.get(follower.id, followed.id)
    if follow is not None and follow.state == PENDING:
        await repos.follows.remove(follower.id, followed.id)
        await repos.commit()
        log.info("follow_rejected", extra={"follower_id": follower.id, "followed_id": followed.id})

async def acept_all_pending(repos: Repos, followed: Actor) -> None:
    """Al hacer pública una cuenta privada se aceptan sus solicitudes. Sin commit."""
    for follower in await repos.follows.requests(followed.id):
        await _accept(repos, await repos.follows.get(follower.id, followed.id), follower, followed)