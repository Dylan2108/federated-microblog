import logging
import uuid

from app.domain.entities import Actor, Note, VISIBILITIES, Repost, utcnow, base_url
from app.domain.ports import Repos
from app.services import timeline, privacy, activities

log = logging.getLogger(__name__)

class InvalidVisibility(ValueError):
    pass

class NoteNotFound(Exception):
    """No existe o el usuario no puede verla """

class NotAuthor(Exception):
    pass

class NotRepostable(Exception):
    pass

async def create(repos: Repos, author: Actor, content: str, visibility: str = "public") -> Note:
    if visibility not in VISIBILITIES:
        raise InvalidVisibility(visibility)
    note = Note(
        id=f"{base_url(repos.domain)}/notes/{uuid.uuid4()}",
        author=author,
        author_id=author.id,
        content=content,
        visibility=visibility
    )
    await repos.notes.add(note)
    await timeline.fan_out(repos, note)
    create = activities.new(repos, "Create", author, activities.note_to_dict(note))
    await activities.send(repos, await activities.remote_followers_domains(repos, author.id), create)
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

async def _visible_or_raise(repos: Repos, note_id: str, viewer: Actor) -> Note:
    note = await get_visible(repos, note_id, viewer)
    if note is None:
        raise NoteNotFound()
    return note

async def edit(repos: Repos, author: Actor, note_id: str, content: str) -> Note:
    """Sólo cambia el contenido y fija `updated`; la visibilidad no se puede cambiar"""
    note = await _visible_or_raise(repos, note_id, author)
    if note.author_id != author.id:
        raise NotAuthor()
    note.edit(content, utcnow())
    update = activities.new(repos, "Update", author, activities.note_to_dict(note))
    await activities.send(repos, await activities.note_copy_domains(repos, note), update)
    await repos.commit()
    log.info("note_updated", extra={"note_id": note.id, "author_id": author.id})
    return note

async def delete(repos: Repos, author: Actor, note_id: str) -> None:
    """Idempotente: borrar otra vez una nota propia ya borrada no hace nada (queda su Tombstone)."""
    note = await get_visible(repos, note_id, author)
    if note is None:
        tombstone = await repos.notes.get_tombstone(note_id)
        if tombstone is not None and tombstone.author_id == author.id:
            return
        raise NoteNotFound()
    if note.author_id != author.id:
        raise NotAuthor()
    domains = await activities.note_copy_domains(repos, note)
    await repos.notes.delete(note)
    delete_ = activities.new(repos, "Delete", author, {"type": "Tombstone", "id": note.id})
    await activities.send(repos, domains, delete_)
    await repos.commit()
    log.info("note_deleted", extra={"note_id": note.id, "author_id": author.id})

async def repost(repos: Repos, actor: Actor, note_id: str) -> None:
    """Idempotente: republicar dos veces la misma nota no hace nada la segunda."""
    note = await _visible_or_raise(repos, note_id, actor)
    if not privacy.can_repost(note):
        raise NotRepostable()
    if await repos.reposts.exists(actor.id, note.id):
        return
    new = Repost(actor_id=actor.id, note_id=note.id)
    repos.reposts.add(new)
    await timeline.fan_out_repost(repos, new)
    announce = activities.new(
        repos, "Announce", actor, activities.note_to_dict(note), published = new.published.isoformat()
    )
    await activities.send(repos, await _repost_domains(repos, actor, note), announce)
    await repos.commit()
    log.info("note_reposted", extra={"note_id": note.id, "actor_id": actor.id})

async def unrepost(repos: Repos, actor: Actor, note_id: str) -> None:
    """Idempotente: deshacer una republicación que no existe no hace nada."""
    note = await _visible_or_raise(repos, note_id, actor)
    if not await repos.reposts.exists(actor.id, note.id):
        return
    await repos.reposts.remove(actor.id, note.id)
    await timeline.remove_repost(repos, actor.id, note)
    undo = activities.new(repos, "Undo", actor, {"type": "Announce", "object": note.id})
    await activities.send(repos, await _repost_domains(repos, actor, note), undo)
    await repos.commit()
    log.info("repost_removed", extra={"note_id": note.id, "actor_id": actor.id})

async def _repost_domains(repos: Repos, actor: Actor, note: Note) -> set[str]:
    """Una republicación va a los servidores de los seguidores de quien republica y al del autor
    (que así sabe adónde enviar después la edición o el borrado de su nota)."""
    domains = await activities.remote_followers_domains(repos, actor.id)
    return domains if note.author.is_local else domains | {note.author.domain}