"""Seguir y dejar de seguir, y solicitudes a cuentas privadas.

Un seguimiento a una cuenta privada (`locked`) queda `pending` hasta que el seguido lo acepta. Sólo uno
`accepted` cuenta como seguidor: llena la home (backfill y fan-out) y da acceso a las notas `followers`.

Con usuarios de otros servidores, cada servidor guarda su copia del `Follow`: el del seguidor lo crea
`pending` y envía `Follow`; el del seguido decide y responde `Accept` o `Reject`.
Las funciones `on_*` aplican lo que llega del otro servidor (las llama services/inbox.py).
"""

import logging
from app.domain.entities import Actor, Follow, ACCEPTED, PENDING
from app.domain.ports import Repos
from app.services import timeline, activities

log = logging.getLogger(__name__)

class CannotFollowSelf(Exception):
    pass

class NoFollowRequest(Exception):
    pass

async def follow(repos: Repos, follower: Actor, followed: Actor) -> str:
    """Devuelve el estado del seguimiento. Idempotente: seguir otra vez devuelve el estado que ya tenía.
    Lo usan tanto un usuario local como un `Follow` recibido de otro servidor.
    """
    if follower.id == followed.id:
        raise CannotFollowSelf()
    existing = await repos.follows.get(follower.id, followed.id)
    if existing is not None:
        return existing.state
    follow = Follow(follower_id=follower.id, followed_id=followed.id, state=PENDING)
    repos.follows.add(follow)
    if not followed.is_local:
        await activities.send(
            repos, {followed.domain}, activities.new(repos, "Follow", follower, followed.id)

        )
    elif not followed.locked:
        await _accept(repos, follow, follower, followed)
    await repos.commit()
    log.info("follow_created", extra={"follower_id": follower.id, "followed_id": followed.id, "state": follow.state})
    return follow.state

async def unfollow(repos: Repos, follower: Actor, followed: Actor) -> None:
    """También cancela una solicitud pendiente."""
    existed = await repos.follows.get(follower.id, followed.id)
    await repos.follows.remove(follower.id, followed.id)
    await timeline.remove_author(repos, follower, followed)
    if existed and not followed.is_local:
        undo = activities.new(repos, "Undo", follower, activities.follow_object(follower, followed))
        await activities.send(repos, {followed.domain}, undo)
    await repos.commit()
    log.info("follow_removed", extra={"follower_id": follower.id, "followed_id": followed.id})

async def followers(repos: Repos, actor: Actor) -> list[Actor]:
    return await repos.follows.followers(actor.id)

async def following(repos: Repos, actor: Actor) -> list[Actor]:
    return await repos.follows.following(actor.id)

async def requests(repos: Repos, actor: Actor) -> list[Actor]:
    return await repos.follows.requests(actor.id)

async def _accept(repos: Repos, follow: Follow, follower: Actor, followed: Actor) -> None:
    """El seguido (local) acepta. Sin commit: lo hace quien la llama."""
    follow.state = ACCEPTED
    if follower.is_local:
        await timeline.backfill(repos, follower, followed)
    else:
        # El servidor del seguidor recibe la confirmación y, como backfill, las últimas notas del seguido.
        accept = activities.new(repos, "Accept", followed, activities.follow_object(follower, followed))
        await activities.send(repos, {follower.domain}, accept)
        for note in reversed(await repos.notes.recent_by_author(followed.id, timeline.BACKFILL)):
            create = activities.new(repos, "Create", followed, activities.note_to_dict(note))
            await activities.send(repos, {follower.domain}, create)
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
        if not follower.is_local:
            reject_ = activities.new(repos, "Reject", followed, activities.follow_object(follower, followed))
            await activities.send(repos, {follower.domain}, reject_)
        await repos.commit()
        log.info("follow_rejected", extra={"follower_id": follower.id, "followed_id": followed.id})

async def acept_all_pending(repos: Repos, followed: Actor) -> None:
    """Al hacer pública una cuenta privada se aceptan sus solicitudes. Sin commit."""
    for follower in await repos.follows.requests(followed.id):
        await _accept(repos, await repos.follows.get(follower.id, followed.id), follower, followed)

# ---------- respuestas del servidor del seguido (sin commit: lo hace inbox) ----------
async def on_accept(repos: Repos, follower: Actor, followed: Actor) -> None:
    follow = await repos.follows.get(follower.id, followed.id)
    if follow is not None and follow.state == PENDING:
        follow.state = ACCEPTED
        await timeline.backfill(repos, follower, followed)
        log.info("follow_accepted", extra={"follower_id": follower.id, "followed_id": followed.id})

async def on_reject(repos: Repos, follower: Actor, followed: Actor) -> None:
    follow = await repos.follows.get(follower.id, followed.id)
    if follow is not None and follow.state == PENDING:
        await repos.follows.remove(follower.id, followed.id)
        log.info("follow_rejected", extra={"follower_id": follower.id, "followed_id": followed.id})