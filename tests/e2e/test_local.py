import httpx

from conftest import SERVERS

def test_me_returns_logged_user(user):
    ana = user()
    assert ana.http.get("/me").json()["username"] == ana.username

def test_duplicate_username_rejected(user):
    ana = user()
    resp = ana.http.post("/register", json={"username": ana.username, "password": "secreto1"})
    assert resp.status_code == 409

def test_invalid_token_rejected():
    resp = httpx.get(f"{SERVERS['a']}/api/me", headers={"Authorization": "Bearer basura"})
    assert resp.status_code == 401

def test_note_length_limit(user):
    ana = user()
    assert ana.http.post("/notes", json={"content": "x" * 501}).status_code == 422
    assert ana.http.post("/notes", json={"content": ""}).status_code == 422

def test_own_notes_in_home(user):
    ana = user()
    ana.post("mia")
    assert ana.home() == ["mia"]

def test_follow_backfills_and_fans_out(user):
    ana, beto = user(), user()
    beto.post("antes")
    ana.http.post(f"/users/{beto.username}/follow")
    assert ana.home() == ["antes"]
    beto.post("después")
    assert ana.home() == ["después", "antes"]

def test_unfollowed_notes_leave_home(user):
    ana, beto = user(), user()
    ana.http.post(f"/users/{beto.username}/follow")
    beto.post("hola")
    ana.post("propia")
    ana.http.delete(f"/users/{beto.username}/follow")
    assert ana.home() == ["propia"]

def test_non_followers_do_not_receive(user):
    ana, beto = user(), user()
    beto.post("Solo para mis seguidores")
    assert ana.home() == []

def test_cannot_follow_self(user):
    ana = user()
    assert ana.http.post(f"/users/{ana.username}/follow").status_code == 400

def test_servers_are_independent(user):
    beto = user("b")
    assert httpx.get(f"{SERVERS['a']}/api/users/{beto.username}").status_code == 404