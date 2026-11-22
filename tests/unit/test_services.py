"""Lógica de services/ probada con el adaptador en memoria: sin Docker ni Postgres."""

import asyncio
from datetime import timedelta
import pytest
from app.domain.entities import Actor, Follow, Note
from app.services import follows, notes, timeline, users
from app.repositories.memory import MemoryRepos

run = asyncio.run

@pytest.fixture
def repos():
    return MemoryRepos()

def register(repos, username):
    return run(users.register(repos, username, "secreto1", ""))

def remote_actor(repos, username):
    actor = Actor(id=f"http://server-b:8000/users/{username}", username=username, domain="server-b", is_local=False)
    repos.actors.add(actor)
    return actor

def home(repos, actor):
    return [n.content for n, _ in run(timeline.home(repos, actor))]

def home_with_reposts(repos, actor):
    """[(contenido, quién la republicó o None)]"""
    return [(n.content, by and by.username) for n, by in run(timeline.home(repos, actor))]

# ---------- usuarios ----------
def test_register_defaults_display_name_and_commits(repos):
    ana = register(repos, "ana")
    assert ana.display_name == "ana" and ana.is_local
    assert repos.commits == 1

def test_register_duplicate_rejected(repos):
    register(repos, "ana")
    with pytest.raises(users.UsernameTaken):
        register(repos, "ana")

def test_authenticate(repos):
    register(repos, "ana")
    assert run(users.authenticate(repos, "ana", "secreto1")).username == "ana"
    assert run(users.authenticate(repos, "ana", "otra")) is None
    assert run(users.authenticate(repos, "nadie", "secreto1")) is None

# ---------- seguimiento ----------
def test_cannot_follow_self(repos):
    ana = register(repos, "ana")
    with pytest.raises(follows.CannotFollowSelf):
        run(follows.follow(repos, ana, ana))

def test_follow_is_idempotent_and_commits_once(repos):
    ana, beto = register(repos, "ana"), register(repos, "beto")
    before = repos.commits
    run(follows.follow(repos, ana, beto))
    run(follows.follow(repos, ana, beto))
    assert repos.commits == before + 1
    assert [a.username for a in run(follows.followers(repos, beto))] == ["ana"]

def test_follow_backfills_home(repos):
    ana, beto = register(repos, "ana"), register(repos, "beto")
    run(notes.create(repos, beto, "antes"))
    run(follows.follow(repos, ana, beto))
    assert home(repos, ana) == ["antes"]

def test_unfollow_removes_author_notes_only(repos):
    ana, beto = register(repos, "ana"), register(repos, "beto")
    run(follows.follow(repos, ana, beto))
    run(notes.create(repos, beto, "de beto"))
    run(notes.create(repos, ana, "de ana"))
    run(follows.unfollow(repos, ana, beto))
    assert home(repos, ana) == ["de ana"]
    assert run(follows.following(repos, ana)) == []

# ---------- publicaciones y fan-out ----------
def test_fan_out_reaches_author_and_local_followers_only(repos):
    ana, beto, carla = register(repos, "ana"), register(repos, "beto"), register(repos, "carla")
    remoto = remote_actor(repos, "remoto")
    run(follows.follow(repos, beto, ana))
    repos.follows.add(Follow(follower_id=remoto.id, followed_id=ana.id))
    run(notes.create(repos, ana, "hola"))
    owners = {o for o, _ in repos.timeline.entries}
    assert owners == {ana.id, beto.id}
    assert home(repos, carla) == []

def test_home_is_newest_first(repos):
    ana = register(repos, "ana")
    for text in ["1", "2", "3"]:
        run(notes.create(repos, ana, text))
    assert home(repos, ana) == ["3", "2", "1"]

# ---------- visibilidad y privacidad ----------
def publish(repos, author, content, visibility="public"):
    return run(notes.create(repos, author, content, visibility))

def profile(repos, author, viewer):
    return [n.content for n in run(notes.by_author(repos, author, viewer))]

def test_invalid_visibility_rejected(repos):
    ana = register(repos, "ana")
    with pytest.raises(notes.InvalidVisibility):
        publish(repos, ana, "x", "secreta")

def test_profile_hides_followers_notes_from_non_followers(repos):
    ana, beto = register(repos, "ana"), register(repos, "beto")
    publish(repos, ana, "pública")
    publish(repos, ana, "no listada", "unlisted")
    publish(repos, ana, "solo seguidores", "followers")
    assert profile(repos, ana, None) == ["no listada", "pública"]
    assert profile(repos, ana, beto) == ["no listada", "pública"]
    run(follows.follow(repos, beto, ana))
    assert profile(repos, ana, beto) == ["solo seguidores", "no listada", "pública"]
    assert profile(repos, ana, ana) == ["solo seguidores", "no listada", "pública"]

def test_get_visible_hides_followers_note_without_revealing_it(repos):
    ana, beto = register(repos, "ana"), register(repos, "beto")
    note = publish(repos, ana, "secreto", "followers")
    assert run(notes.get_visible(repos, note.id, None)) is None
    assert run(notes.get_visible(repos, note.id, beto)) is None
    assert run(notes.get_visible(repos, "http://x/notes/no-existe", beto)) is None
    run(follows.follow(repos, beto, ana))
    assert run(notes.get_visible(repos, note.id, beto)).content == "secreto"

def test_followers_note_reaches_followers_home_only(repos):
    ana, beto, carla = register(repos, "ana"), register(repos, "beto"), register(repos, "carla")
    run(follows.follow(repos, beto, ana))
    publish(repos, ana, "para seguidores", "followers")
    assert home(repos, beto) == ["para seguidores"]
    assert home(repos, carla) == []

def test_local_and_federated_timelines_only_show_public(repos):
    ana = register(repos, "ana")
    remoto = remote_actor(repos, "remoto")
    publish(repos, ana, "publica local")
    publish(repos, ana, "no listada", "unlisted")
    publish(repos, ana, "seguidores", "followers")
    run(repos.notes.add(Note(id="http://server-b:8000/notes/1", author=remoto, author_id= remoto.id, content="publica remota")))
    local = [n.content for n in run(timeline.local(repos))]
    federated = [n.content for n in run(timeline.federated(repos))]
    assert local == ["publica local"]
    assert sorted(federated) == ["publica local", "publica remota"]

# ---------- republicar, editar y borrar ----------
def test_repost_reaches_reposter_followers_with_reposted_by(repos):
    ana, beto, carla = register(repos, "ana"), register(repos, "beto"), register(repos, "carla")
    run(follows.follow(repos, carla, beto))
    note = publish(repos, ana, "de ana")
    run(notes.repost(repos, beto, note.id))
    assert home_with_reposts(repos, carla) == [("de ana", "beto")]
    assert home_with_reposts(repos, beto) == [("de ana", "beto")]

def test_repost_does_not_duplicate_in_home_and_is_idempotent(repos):
    ana, beto, carla = register(repos, "ana"), register(repos, "beto"), register(repos, "carla")
    run(follows.follow(repos, carla, ana))
    run(follows.follow(repos, carla, beto))
    note = publish(repos, ana, "de ana")
    before = repos.commits
    run(notes.repost(repos, beto, note.id))
    run(notes.repost(repos, beto, note.id))
    assert repos.commits == before + 1
    assert home_with_reposts(repos, carla) == [("de ana", "beto")]

def test_repost_is_ordered_by_repost_date(repos):
    ana, beto = register(repos, "ana"), register(repos, "beto")
    old = publish(repos, ana, "antigua")
    publish(repos, beto, "propia")
    run(notes.repost(repos, beto, old.id))
    assert home(repos, beto) == ["antigua", "propia"]

def test_followers_note_cannot_be_reposted(repos):
    ana, beto = register(repos, "ana"), register(repos, "beto")
    run(follows.follow(repos, beto, ana))
    note = publish(repos, ana, "secreto", "followers")
    with pytest.raises(notes.NotRepostable):
        run(notes.repost(repos, beto, note.id))

def test_unrepost_keeps_note_for_who_follows_author(repos):
    ana, beto, carla, dani = (register(repos, n) for n in ("ana", "beto", "carla", "dani"))
    run(follows.follow(repos, carla, ana))
    run(follows.follow(repos, carla, beto))
    run(follows.follow(repos, dani, beto))
    note = publish(repos, ana, "de ana")
    run(notes.repost(repos, beto, note.id))
    run(notes.unrepost(repos, beto, note.id))
    run(notes.unrepost(repos, beto, note.id))
    assert home_with_reposts(repos, carla) == [("de ana", None)] #Sigue a la autora
    assert home(repos, dani) == []

def test_unrepost_falls_back_to_another_repost(repos):
    ana, beto, carla, dani = (register(repos, n) for n in ("ana", "beto", "carla", "dani"))
    run(follows.follow(repos, dani, beto))
    run(follows.follow(repos, dani, carla))
    note = publish(repos, ana, "de ana")
    run(notes.repost(repos, carla, note.id))
    run(notes.repost(repos, beto, note.id))
    run(notes.unrepost(repos, beto, note.id))
    assert home_with_reposts(repos, dani) == [("de ana", "carla")]

def test_edit_only_by_author_and_sets_updated(repos):
    ana, beto = register(repos, "ana"), register(repos, "beto")
    note = publish(repos, ana, "original")
    with pytest.raises(notes.NotAuthor):
        run(notes.edit(repos, beto, note.id, "pirata"))
    edited = run(notes.edit(repos, ana, note.id, "editada"))
    assert edited.content == "editada" and edited.updated is not None
    assert home(repos, ana) == ["editada"]

def test_edit_hidden_note_is_not_found(repos):
    ana, beto = register(repos, "ana"), register(repos, "beto")
    note = publish(repos, ana, "secreto", "followers")
    with pytest.raises(notes.NoteNotFound):  # 404, no 403: no revela que existe
        run(notes.edit(repos, beto, note.id, "x"))

def test_edit_last_writer_wins():
    ana = Actor(id="http://a/users/ana", username="ana", domain="a", is_local=True)
    note = Note(id="http://a/notes/1", author_id=ana.id, author=ana, content="v0")
    t = note.published
    assert note.edit("v2", t + timedelta(seconds=2))
    assert not note.edit("v1", t + timedelta(seconds=1))  # edición antigua que llega tarde
    assert note.content == "v2"

def test_delete_removes_note_reposts_and_home_entries(repos):
    ana, beto, carla = register(repos, "ana"), register(repos, "beto"), register(repos, "carla")
    run(follows.follow(repos, carla, beto))
    note = publish(repos, ana, "efímera")
    run(notes.repost(repos, beto, note.id))
    run(notes.delete(repos, ana, note.id))
    assert home(repos, ana) == home(repos, beto) == home(repos, carla) == []
    assert run(repos.reposts.of_note(note.id)) == []
    assert run(notes.get_visible(repos, note.id, ana)) is None
    assert run(repos.notes.get_tombstone(note.id)).author_id == ana.id

def test_delete_is_idempotent_for_author_only(repos):
    ana, beto = register(repos, "ana"), register(repos, "beto")
    note = publish(repos, ana, "x")
    with pytest.raises(notes.NotAuthor):
        run(notes.delete(repos, beto, note.id))
    run(notes.delete(repos, ana, note.id))
    run(notes.delete(repos, ana, note.id))  # ya borrada: sin error
    with pytest.raises(notes.NoteNotFound):
        run(notes.delete(repos, beto, note.id))

# ---------- cuentas privadas y solicitudes ----------

def private(repos, username):
    actor = register(repos, username)
    run(users.update_profile(repos, actor, locked=True))
    return actor


def names(actors):
    return [a.username for a in actors]


def test_follow_public_account_is_accepted(repos):
    ana, beto = register(repos, "ana"), register(repos, "beto")
    assert run(follows.follow(repos, ana, beto)) == "accepted"
    assert run(follows.follow(repos, ana, beto)) == "accepted"  # idempotente


def test_private_account_gains_no_follower_until_accepted(repos):
    ana, beto = register(repos, "ana"), private(repos, "beto")
    publish(repos, beto, "para seguidores", "followers")
    assert run(follows.follow(repos, ana, beto)) == "pending"
    assert run(follows.follow(repos, ana, beto)) == "pending"
    assert names(run(follows.followers(repos, beto))) == []
    assert names(run(follows.following(repos, ana))) == []
    assert names(run(follows.requests(repos, beto))) == ["ana"]
    # un seguidor pendiente no ve notas `followers` ni recibe nada en su home
    assert profile(repos, beto, ana) == []
    publish(repos, beto, "nueva", "followers")
    assert home(repos, ana) == []


def test_accept_request_backfills_and_is_idempotent(repos):
    ana, beto = register(repos, "ana"), private(repos, "beto")
    publish(repos, beto, "antes", "followers")
    run(follows.follow(repos, ana, beto))
    run(follows.accept(repos, beto, ana))
    run(follows.accept(repos, beto, ana))
    assert names(run(follows.followers(repos, beto))) == ["ana"]
    assert names(run(follows.requests(repos, beto))) == []
    assert home(repos, ana) == ["antes"]
    assert profile(repos, beto, ana) == ["antes"]


def test_accept_without_request_fails(repos):
    ana, beto = register(repos, "ana"), private(repos, "beto")
    with pytest.raises(follows.NoFollowRequest):
        run(follows.accept(repos, beto, ana))


def test_reject_request_is_idempotent_and_keeps_accepted_followers(repos):
    ana, beto, carla = register(repos, "ana"), private(repos, "beto"), register(repos, "carla")
    run(follows.follow(repos, ana, beto))
    run(follows.follow(repos, carla, beto))
    run(follows.accept(repos, beto, carla))
    run(follows.reject(repos, beto, ana))
    run(follows.reject(repos, beto, ana))    # ya no hay solicitud: sin efecto
    run(follows.reject(repos, beto, carla))  # no echa a un seguidor aceptado
    assert names(run(follows.requests(repos, beto))) == []
    assert names(run(follows.followers(repos, beto))) == ["carla"]


def test_unfollow_cancels_pending_request(repos):
    ana, beto = register(repos, "ana"), private(repos, "beto")
    run(follows.follow(repos, ana, beto))
    run(follows.unfollow(repos, ana, beto))
    assert names(run(follows.requests(repos, beto))) == []


def test_unlocking_accepts_pending_requests(repos):
    ana, beto = register(repos, "ana"), private(repos, "beto")
    publish(repos, beto, "hola")
    run(follows.follow(repos, ana, beto))
    run(users.update_profile(repos, beto, locked=False))
    assert names(run(follows.followers(repos, beto))) == ["ana"]
    assert home(repos, ana) == ["hola"]


def test_update_profile_changes_only_given_fields(repos):
    ana = register(repos, "ana")
    run(users.update_profile(repos, ana, display_name="Ana"))
    assert ana.display_name == "Ana" and not ana.locked
    assert ana.handle == f"ana@{ana.domain}"
