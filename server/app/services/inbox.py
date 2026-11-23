"""Recepción de actividades de otros servidores (el "buzón de entrada").

`receive` es idempotente por el `id` de la actividad: si ya se procesó, no hace nada. El id se guarda en
la misma transacción que sus efectos. Una actividad no válida o no autorizada se descarta y se registra
(`activity_rejected`); también se guarda su id, para no reevaluarla si llega otra vez.

Autorización mínima: el actor debe pertenecer a su dominio y sólo puede actuar sobre lo suyo (el autor
edita o borra su nota, el seguido acepta). Que el actor sea quien dice ser lo garantizarán las firmas (F2).
"""

import logging
from datetime import datetime
from app.domain.entities import Actor, Repost, Tombstone
from app.domain.ports import Repos
from app.services import activities, follows, privacy, timeline
from app.services.activities import InvalidActivity

log = logging.getLogger(__name__)

async def receive(repos: Repos, activity: dict) -> None:
    ids = {"activity_id": activity.get("id"), "type": activity.get("type")}
    if await repos.activities.seen(activity["id"]):
        log.info("activity_duplicate", extra=ids)
        return
    log.info("activity_received", extra=ids)
    await repos.activities.add(activity["id"])
    try:
        handler = _HANDLERS.get(_kind(activity))
        if handler is None:
            raise InvalidActivity(f"tipo no soportado: {_kind(activity)}" )
        await handler(repos, activity)
    except (InvalidActivity, KeyError, TypeError, ValueError) as exc:
        log.warning("activity_rejected", extra={**ids, "reason": f"{type(exc).__name__}: {exc}"})
        await repos.commit()

def _kind(activity: dict) -> str:
    if activity["type"] == "Undo":
        return f"Undo.{activity['object']['type']}"
    return activity["type"]

async def _local(repos: Repos, actor_id: str) -> Actor:
    actor = await repos.actors.get(actor_id)
    if actor is None or not actor.is_local:
        raise InvalidActivity(f"no es un usuario de este servidor: {actor_id}")
    return actor

# ---------- seguimiento ----------
async def _follow(repos, activity):
    follower = await activities.remote_actor(repos, activity["actor"])
    await follows.follow(repos, follower, await _local(repos, activity["object"]))

async def _follow_response(repos, activity):
    """Accept o Reject del servidor del seguido; sólo el seguido puede responder."""
    followed = await activities.remote_actor(repos, activity["actor"])
    if activity["object"]["object"] != followed.id:
        raise InvalidActivity("sólo el seguido responde a una solicitud")
    follower = await _local(repos, activity["object"]["actor"])
    handler = follows.on_accept if activity["type"] == "Accept" else follows.on_reject
    await handler(repos, follower, followed)

async def _undo_follow(repos, activity):
    follower = await activities.remote_actor(repos, activity["actor"])
    if activity["object"]["actor"] != follower.id:
        raise InvalidActivity("sólo el seguidor deshace su seguimiento")
    await follows.unfollow(repos, follower, await _local(repos, activity["object"]["object"]))

# ---------- notas ----------

async def _known_note(repos: Repos, data: dict):
    """La nota de `data`: la copia que ya tenemos o una nueva. None si fue borrada (tombstone)."""
    if await repos.notes.get_tombstone(data["id"]) is not None:
        return None
    note = await repos.notes.get(data["id"])
    if note is None:
        if data["attributedTo"]["domain"] == repos.domain:
            raise InvalidActivity(f"nota local desconocida: {data['id']}")
        author = await activities.remote_actor(repos, data["attributedTo"])
        note = activities.note_from_dict(data, author)
        await repos.notes.add(note)
    return note


async def _create(repos, activity):
    author = await activities.remote_actor(repos, activity["actor"])
    if activity["object"]["attributedTo"]["id"] != author.id:
        raise InvalidActivity("sólo el autor publica su nota")
    note = await _known_note(repos, activity["object"])
    if note is None:
        raise InvalidActivity(f"nota ya borrada: {activity['object']['id']}")
    await timeline.fan_out(repos, note)  # idempotente: una nota está una sola vez en cada home


async def _update(repos, activity):
    author = await activities.remote_actor(repos, activity["actor"])
    data = activity["object"]
    note = await repos.notes.get(data["id"])
    if note is None:
        return  # no la tenemos (o está borrada): nada que actualizar
    if note.author_id != author.id:
        raise InvalidActivity("sólo el autor edita su nota")
    if note.edit(data["content"], datetime.fromisoformat(data["updated"])):  # last-writer-wins
        await _forward(repos, note, activity)


async def _delete(repos, activity):
    author = await activities.remote_actor(repos, activity["actor"])
    note_id = activity["object"]["id"]
    if not activities.owned_by(note_id, author.domain):
        raise InvalidActivity("sólo el autor borra su nota")
    note = await repos.notes.get(note_id)
    if note is None:
        if await repos.notes.get_tombstone(note_id) is None:  # el borrado llegó antes que la nota
            await repos.notes.add_tombstone(Tombstone(id=note_id, author_id=author.id))
        return
    if note.author_id != author.id:
        raise InvalidActivity("sólo el autor borra su nota")
    domains = await activities.note_copy_domains(repos, note)  # antes de borrar sus republicaciones
    await repos.notes.delete(note)
    await activities.send(repos, domains, activity)


async def _forward(repos: Repos, note, activity: dict) -> None:
    """Reenvía la actividad a los servidores que recibieron la nota desde aquí (por una republicación
    de un usuario local). Mismo id: quien ya la tenga la descarta como duplicada."""
    await activities.send(repos, await activities.note_copy_domains(repos, note), activity)


# ---------- republicaciones ----------

async def _announce(repos, activity):
    actor = await activities.remote_actor(repos, activity["actor"])
    note = await _known_note(repos, activity["object"])
    if note is None:
        return  # republicación de una nota borrada
    if not privacy.can_repost(note):
        raise InvalidActivity("las notas followers no se pueden republicar")
    if not await repos.reposts.exists(actor.id, note.id):
        repost = Repost(actor_id=actor.id, note_id=note.id, published=datetime.fromisoformat(activity["published"]))
        repos.reposts.add(repost)
        await timeline.fan_out_repost(repos, repost)


async def _undo_announce(repos, activity):
    actor = await activities.remote_actor(repos, activity["actor"])
    note = await repos.notes.get(activity["object"]["object"])
    if note is not None and await repos.reposts.exists(actor.id, note.id):
        await repos.reposts.remove(actor.id, note.id)
        await timeline.remove_repost(repos, actor.id, note)

_HANDLERS = {
    "Follow": _follow,
    "Accept": _follow_response,
    "Reject": _follow_response,
    "Undo.Follow": _undo_follow,
    "Create": _create,
    "Update": _update,
    "Delete": _delete,
    "Announce": _announce,
    "Undo.Announce": _undo_announce,
}