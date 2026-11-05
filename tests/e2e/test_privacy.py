import uuid
import httpx
from conftest import SERVERS

API = f"{SERVERS['a']}/api"

def contents(resp: httpx.Response) -> list[str]:
    assert resp.status_code == 200, resp.text
    return [n["content"] for n in resp.json()]

def unique(text: str) -> str:
    return f"{text}-{uuid.uuid4().hex[:8]}"

def test_followers_note_hidden_from_anonymous_and_non_followers(user):
    ana, beto = user(), user()
    secret = unique("secreto")
    note = ana.post(secret, visibility="followers")
    assert note["visibility"] == "followers"

    assert secret not in contents(httpx.get(f"{API}/users/{ana.username}/notes"))
    assert secret not in contents(beto.http.get(f"{API}/users/{ana.username}/notes"))
    assert httpx.get(f"{API}/notes", params={"id": note["id"]}).status_code == 404
    assert beto.http.get("/notes", params={"id": note["id"]}).status_code == 404
    assert secret not in beto.home()

def test_followers_note_visible_to_follower_and_author(user):
    ana, beto = user(), user()
    beto.http.post(f"/users/{ana.username}/follow")
    secret = unique("para seguidores")
    note = ana.post(secret, "followers")

    assert secret in beto.home()
    assert secret in contents(beto.http.get(f"/users/{ana.username}/notes"))
    assert beto.http.get("/notes", params={"id": note["id"]}).json()["content"] == secret
    assert secret in contents(ana.http.get(f"/users/{ana.username}/notes"))

def test_public_timelines_only_show_public_notes(user):
    ana = user()
    public, unlisted, followers = unique("pub"), unique("unl"), unique("fol")
    ana.post(public)
    ana.post(unlisted, "unlisted")
    ana.post(followers, "followers")

    for timeline in ("local", "federated"):
        seen = contents(httpx.get(f"{API}/timelines/{timeline}", params={"limit": 200}))
        assert public in seen and unlisted not in seen and followers not in seen
    profile = contents(httpx.get(f"{API}/users/{ana.username}/notes"))
    assert public in profile and unlisted in profile and followers not in profile

def test_invalid_visibility_rejected(user):
    ana = user()
    resp = ana.http.post("/notes", json={"content": "x", "visibility": "secreta"})
    assert resp.status_code == 422

def test_invalid_token_on_optional_auth_endpoint_is_401(user):
    ana = user()
    resp = httpx.get(f"{API}/users/{ana.username}/notes", headers={"Authorization": "Bearer basura"})
    assert resp.status_code == 401