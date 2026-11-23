"""Actividades entre servidores: su formato y su envío por el puerto Federation.

Formato inspirado en ActivityPub, pero propio (no se afirma compatibilidad): un dict JSON con
`id` global (identifica la actividad: recibirla dos veces no tiene efecto), `type`, `actor` y `object`.
El actor y la nota viajan embebidos para que el receptor no tenga que preguntar al emisor.
Tipos: Follow, Accept, Reject, Undo(Follow), Create, Update, Delete, Announce, Undo(Announce).
"""

import logging
import uuid
from datetime import datetime
from app.domain.entities import VISIBILITIES, Actor, Note, base_url
from app.domain.ports import Repos

log = logging.getLogger(__name__)

class InvalidActivity(Exception):
    """Actividad mal formada o no autorizada: se descarta (y se registra)."""

# ---------- formato ----------
def actor_to_dict(actor: Actor) -> dict:
    return {
        "id": actor.id, "username": actor.username, "domain": actor.domain,
        "display_name": actor.display_name, "locked": actor.locked
    }

def note_to_dict(note: Note) -> dict:
    return {
        "type": "Note",
        "id": note.id,
        "attributedTo": actor_to_dict(note.author),
        "content": note.content,
        "visibility": note.visibility,
        "published": note.published.isoformat(),
        "updated": note.updated and note.updated.isoformat()
    }

def follow_object(follower: Actor, followed: Actor) -> dict:
    return {"type": "Follow", "actor": follower.id, "object": followed.id}

def new(repos: Repos, type_: str, actor: Actor, obj, **extra) -> dict:
    return {
        "id": f"{base_url(repos.domain)}/activities/{uuid.uuid4()}",
        "type": type_,
        "actor": actor_to_dict(actor),
        "object": obj,
        **extra,
    }

def owned_by(object_id: str, domain: str) -> bool:
    """Los ids son URLs: un objeto pertenece al servidor cuyo base_url lo prefija."""
    return object_id.startswith(base_url(domain) + "/")

async def remote_actor(repos: Repos, data: dict) -> Actor:
    """El actor remoto descrito en `data`, creado o actualizado en este servidor."""
    if data["domain"] == repos.domain or not owned_by(data["id"], data["domain"]):
        raise InvalidActivity(f"actor no valido: {data["id"]}")
    actor = await repos.actors.get(data["id"])
    if actor is None:
        actor = Actor(id=data["id"], username=data["username"], domain=data["domain"], is_local=False)
        await repos.actors.add(actor)
    actor.display_name = data.get("display_name") or data["username"]
    actor.locked = bool(data.get("locked"))
    return actor

def note_from_dict(data: dict, author: Actor) -> Note:
    if data["attributedTo"]["id"] != author.id or not owned_by(data["id"], author.domain):
        raise InvalidActivity(f"la nota {data['id']} no es de {author.id}")
    if data["visibility"] not in VISIBILITIES:
        raise InvalidActivity(f"visibilidad no valida: {data['visibility']}")
    return Note(
        id=data["id"], author=author, author_id=author.id, content=data["content"],
        visibility=data["visibility"], published=datetime.fromisoformat(data["published"],),
        updated=data["updated"] and datetime.fromisoformat(data["updated"]),
    )

# ---------- destinatarios y envío ----------
async def remote_followers_domains(repos: Repos, actor_id: str) -> set[str]:
    """Servidores donde `actor_id` tiene seguidores aceptados."""
    return {a.domain for a in await repos.follows.followers(actor_id) if not a.is_local}

async def note_copy_domains(repos: Repos, note: Note) -> set[str]:
    """Servidores a los que esta nota pudo llegar desde aquí: los de los seguidores del autor y, por cada
    republicación, el servidor de quien republicó o, si es local, los de sus seguidores.
    Ahí deben llegar sus ediciones y su borrado."""
    domains = await remote_followers_domains(repos, note.author_id)
    for repost in await repos.reposts.of_note(note.id):
        reposter = await repos.actors.get(repost.actor_id)
        if reposter.is_local:
            domains |= await remote_followers_domains(repos, reposter.id)
        else:
            domains.add(reposter.domain)
    return domains

async def send(repos: Repos, domains: set[str], activity: dict) -> None:
    """Encarga la entrega a cada servidor (nunca a sí mismo). No espera a que llegue."""
    for domain in sorted(domains - {repos.domain}):
        await repos.federation.deliver(domain, activity)
        log.info("activity_sent", extra={"activity_id": activity["id"], "type": activity["type"], "to": domain})