"""Lógica de services/ probada con el adaptador en memoria: sin Docker ni Postgres."""

import asyncio
import pytest
from app.domain.entities import Actor
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
    return [n.content for n in run(timeline.home(repos, actor))]

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
    repos.follows.add(remoto.id, ana.id)
    run(notes.create(repos, ana, "hola"))
    owners = {o for o, _ in repos.timeline.entries}
    assert owners == {ana.id, beto.id}
    assert home(repos, carla) == []

def test_home_is_newest_first(repos):
    ana = register(repos, "ana")
    for text in ["1", "2", "3"]:
        run(notes.create(repos, ana, text))
    assert home(repos, ana) == ["3", "2", "1"]