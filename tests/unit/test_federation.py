"""Federación entre 3 servidores en memoria: actividades salientes y recepción idempotente."""

import asyncio
import logging

import pytest

from app.domain.ports import ServerUnavailable
from app.services import follows, inbox, notes, timeline, users

from fakes import Network

run = asyncio.run


@pytest.fixture
def net():
    return Network("server-a", "server-b", "server-c")


def register(net, domain, username):
    return run(users.register(net.nodes[domain], username, "secreto1", ""))


def remote(net, domain, handle):
    """El actor de `handle` tal como lo conoce el servidor `domain` (lo pide a su servidor si hace falta)."""
    return run(users.find(net.nodes[domain], handle))


def follow(net, domain, follower, handle):
    state = run(follows.follow(net.nodes[domain], follower, remote(net, domain, handle)))
    run(net.run())
    return state


def home(net, domain, actor):
    return [n.content for n, _ in run(timeline.home(net.nodes[domain], actor))]


def deliveries(net, type_):
    return [(d, a) for d, a in net.delivered if a["type"] == type_]


# ---------- handles y actores remotos ----------

def test_find_remote_handle_fetches_and_caches(net):
    register(net, "server-b", "beto")
    beto = remote(net, "server-a", "@beto@server-b")
    assert beto.handle == "beto@server-b" and not beto.is_local
    assert run(net.nodes["server-a"].actors.get(beto.id)) is beto
    assert remote(net, "server-a", "nadie@server-b") is None
    with pytest.raises(ServerUnavailable):
        remote(net, "server-a", "x@server-z")


# ---------- seguimiento remoto ----------

def test_remote_follow_then_note_reaches_home(net):
    ana = register(net, "server-a", "ana")
    beto = register(net, "server-b", "beto")
    run(notes.create(net.nodes["server-b"], beto, "antes"))

    assert follow(net, "server-a", ana, "beto@server-b") == "pending"  # siempre pending al principio
    a_side = run(net.nodes["server-a"].follows.get(ana.id, beto.id))
    assert a_side.state == "accepted"                                   # tras el Accept
    assert [u.handle for u in run(follows.followers(net.nodes["server-b"], beto))] == ["ana@server-a"]
    assert home(net, "server-a", ana) == ["antes"]                      # backfill

    run(notes.create(net.nodes["server-b"], beto, "después"))
    run(net.run())
    assert home(net, "server-a", ana) == ["después", "antes"]


def test_remote_locked_account_needs_approval(net):
    ana = register(net, "server-a", "ana")
    beto = register(net, "server-b", "beto")
    run(users.update_profile(net.nodes["server-b"], beto, locked=True))
    run(notes.create(net.nodes["server-b"], beto, "secreto", "followers"))

    follow(net, "server-a", ana, "beto@server-b")
    assert run(net.nodes["server-a"].follows.get(ana.id, beto.id)).state == "pending"
    assert home(net, "server-a", ana) == []

    ana_on_b = run(follows.requests(net.nodes["server-b"], beto))[0]
    run(follows.accept(net.nodes["server-b"], beto, ana_on_b))
    run(net.run())
    assert run(net.nodes["server-a"].follows.get(ana.id, beto.id)).state == "accepted"
    assert home(net, "server-a", ana) == ["secreto"]


def test_remote_reject_and_unfollow(net):
    ana, carla = register(net, "server-a", "ana"), register(net, "server-a", "carla")
    beto = register(net, "server-b", "beto")
    run(users.update_profile(net.nodes["server-b"], beto, locked=True))
    follow(net, "server-a", ana, "beto@server-b")
    ana_on_b = run(follows.requests(net.nodes["server-b"], beto))[0]
    run(follows.reject(net.nodes["server-b"], beto, ana_on_b))
    run(net.run())
    assert run(net.nodes["server-a"].follows.get(ana.id, beto.id)) is None

    run(users.update_profile(net.nodes["server-b"], beto, locked=False))
    follow(net, "server-a", carla, "beto@server-b")
    run(follows.unfollow(net.nodes["server-a"], carla, remote(net, "server-a", "beto@server-b")))
    run(net.run())
    assert run(follows.followers(net.nodes["server-b"], beto)) == []


# ---------- notas: visibilidad, edición y borrado ----------

def test_notes_only_go_to_servers_with_followers(net):
    ana = register(net, "server-a", "ana")
    beto = register(net, "server-b", "beto")
    follow(net, "server-a", ana, "beto@server-b")
    run(notes.create(net.nodes["server-b"], beto, "sólo seguidores", "followers"))
    run(net.run())
    assert {d for d, _ in deliveries(net, "Create")} == {"server-a"}
    assert home(net, "server-a", ana) == ["sólo seguidores"]
    assert run(net.nodes["server-c"].notes.recent_by_author(beto.id, 10)) == []


def test_remote_edit_is_last_writer_wins(net):
    ana = register(net, "server-a", "ana")
    beto = register(net, "server-b", "beto")
    follow(net, "server-a", ana, "beto@server-b")
    note = run(notes.create(net.nodes["server-b"], beto, "v1"))
    run(net.run())
    run(notes.edit(net.nodes["server-b"], beto, note.id, "v2"))
    run(net.run())
    run(notes.edit(net.nodes["server-b"], beto, note.id, "v3"))
    old_update = net.queue.pop()  # la edición v3 se retrasa...
    run(notes.edit(net.nodes["server-b"], beto, note.id, "v4"))
    run(net.run())
    net.queue.append(old_update)  # ...y llega después de la v4
    run(net.run())
    assert home(net, "server-a", ana) == ["v4"]


def test_remote_delete_and_late_create_is_rejected(net, caplog):
    ana = register(net, "server-a", "ana")
    beto = register(net, "server-b", "beto")
    follow(net, "server-a", ana, "beto@server-b")
    note = run(notes.create(net.nodes["server-b"], beto, "efímera"))
    create = net.queue.pop()          # la publicación se retrasa
    run(notes.delete(net.nodes["server-b"], beto, note.id))
    run(net.run())                    # llega antes el borrado
    net.queue.append(create)
    with caplog.at_level(logging.WARNING):
        run(net.run())
    assert home(net, "server-a", ana) == []
    assert any(r.msg == "activity_rejected" for r in caplog.records)


# ---------- republicaciones entre servidores ----------

def test_remote_repost_and_delete_reach_reposter_followers(net):
    """beto (b) publica; carla (c) lo sigue y republica; ana (a) sólo sigue a carla.
    El borrado de beto llega a c y c lo reenvía a a, que recibió la nota por la republicación."""
    ana = register(net, "server-a", "ana")
    beto = register(net, "server-b", "beto")
    carla = register(net, "server-c", "carla")
    follow(net, "server-c", carla, "beto@server-b")
    follow(net, "server-a", ana, "carla@server-c")
    note = run(notes.create(net.nodes["server-b"], beto, "de beto"))
    run(net.run())

    run(notes.repost(net.nodes["server-c"], carla, note.id))
    run(net.run())
    [(entry, by)] = run(timeline.home(net.nodes["server-a"], ana))
    assert entry.content == "de beto" and by.handle == "carla@server-c"
    assert {d for d, _ in deliveries(net, "Announce")} == {"server-a", "server-b"}  # seguidores + autor

    run(notes.delete(net.nodes["server-b"], beto, note.id))
    run(net.run())
    assert home(net, "server-a", ana) == [] and home(net, "server-c", carla) == []


def test_remote_undo_repost(net):
    ana = register(net, "server-a", "ana")
    beto = register(net, "server-b", "beto")
    carla = register(net, "server-c", "carla")
    follow(net, "server-c", carla, "beto@server-b")
    follow(net, "server-a", ana, "carla@server-c")
    note = run(notes.create(net.nodes["server-b"], beto, "de beto"))
    run(net.run())
    run(notes.repost(net.nodes["server-c"], carla, note.id))
    run(net.run())
    run(notes.unrepost(net.nodes["server-c"], carla, note.id))
    run(net.run())
    assert home(net, "server-a", ana) == []
    assert run(net.nodes["server-b"].reposts.of_note(note.id)) == []


# ---------- idempotencia y autorización ----------

def test_delivering_twice_has_no_effect(net, caplog):
    ana = register(net, "server-a", "ana")
    beto = register(net, "server-b", "beto")
    follow(net, "server-a", ana, "beto@server-b")
    run(notes.create(net.nodes["server-b"], beto, "una vez"))
    run(net.run())
    with caplog.at_level(logging.INFO):
        for domain, activity in list(net.delivered):  # todo lo entregado, otra vez
            run(inbox.receive(net.nodes[domain], activity))
    assert home(net, "server-a", ana) == ["una vez"]
    assert len(run(follows.followers(net.nodes["server-b"], beto))) == 1
    assert sum(r.msg == "activity_duplicate" for r in caplog.records) == len(net.delivered)


def test_cannot_impersonate_local_user_or_edit_others_notes(net, caplog):
    ana = register(net, "server-a", "ana")
    beto = register(net, "server-b", "beto")
    follow(net, "server-a", ana, "beto@server-b")
    note = run(notes.create(net.nodes["server-b"], beto, "original"))
    run(net.run())
    forged = {
        "id": "http://server-c:8000/activities/x", "type": "Update",
        "actor": {"id": "http://server-c:8000/users/eva", "username": "eva", "domain": "server-c"},
        "object": {"id": note.id, "content": "falsa", "updated": "2999-01-01T00:00:00+00:00"},
    }
    impostor = {**forged, "id": "http://server-c:8000/activities/y", "type": "Follow",
                "actor": {"id": ana.id, "username": "ana", "domain": "server-a"}, "object": beto.id}
    with caplog.at_level(logging.WARNING):
        run(inbox.receive(net.nodes["server-a"], forged))
        run(inbox.receive(net.nodes["server-a"], impostor))
    assert home(net, "server-a", ana) == ["original"]
    assert [r.msg for r in caplog.records].count("activity_rejected") == 2
