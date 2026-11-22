"""republicar, editar y borrar."""
import httpx
from conftest import SERVERS
API = f"{SERVERS['a']}/api"

def home_entries(client) -> list[tuple[str, str | None]]:
    """[(contenido, nombre de quien la republicó o None)]"""
    return [
        (n["content"], n["reposted_by"] and n["reposted_by"]["username"])
        for n in client.http.get("/timelines/home").json()
    ]

def test_repost_appears_once_with_reposted_by(user):
    ana, beto, carla = user(), user(), user()
    carla.http.post(f"/users/{ana.username}/follow")
    carla.http.post(f"/users/{beto.username}/follow")
    note = ana.post("de ana")
    assert beto.http.post("/notes/repost", params={"id": note["id"]}).status_code == 204
    assert beto.http.post("/notes/repost", params={"id": note["id"]}).status_code == 204  # idempotente
    assert home_entries(carla) == [("de ana", beto.username)]

def test_followers_note_cannot_be_reposted(user):
    ana, beto = user(), user()
    beto.http.post(f"/users/{ana.username}/follow")
    note = ana.post("secreto", "followers")
    assert beto.http.post("/notes/repost", params={"id": note["id"]}).status_code == 403

def test_unrepost_removes_it_from_followers_home(user):
    ana, beto, carla = user(), user(), user()
    carla.http.post(f"/users/{beto.username}/follow")
    note = ana.post("de ana")
    beto.http.post("/notes/repost", params={"id": note["id"]})
    assert beto.http.delete("/notes/repost", params={"id": note["id"]}).status_code == 204
    assert beto.http.delete("/notes/repost", params={"id": note["id"]}).status_code == 204
    assert carla.home() == []

def test_edit_sets_updated_and_only_author(user):
    ana, beto = user(), user()
    note = ana.post("original")
    assert note["updated"] is None
    assert beto.http.patch("/notes", params={"id": note["id"]}, json={"content": "x"}).status_code == 403
    resp = ana.http.patch("/notes", params={"id": note["id"]}, json={"content": "editada"})
    assert resp.status_code == 200
    assert resp.json()["content"] == "editada" and resp.json()["updated"] is not None
    assert ana.home() == ["editada"]
    assert ana.http.patch("/notes", params={"id": note["id"]}, json={"content": ""}).status_code == 422

def test_delete_removes_note_and_reposts(user):
    ana, beto, carla = user(), user(), user()
    carla.http.post(f"/users/{beto.username}/follow")
    note = ana.post("efímera")
    beto.http.post("/notes/repost", params={"id": note["id"]})
    assert beto.http.delete("/notes", params={"id": note["id"]}).status_code == 403
    assert ana.http.delete("/notes", params={"id": note["id"]}).status_code == 204
    assert ana.http.delete("/notes", params={"id": note["id"]}).status_code == 204  # idempotente
    assert httpx.get(f"{API}/notes", params={"id": note["id"]}).status_code == 404
    assert ana.home() == beto.home() == carla.home() == []

def test_unknown_note_is_404(user):
    ana = user()
    missing = {"id": "http://server-a:8000/notes/no-existe"}
    assert ana.http.patch("/notes", params=missing, json={"content": "x"}).status_code == 404
    assert ana.http.delete("/notes", params=missing).status_code == 404
    assert ana.http.post("/notes/repost", params=missing).status_code == 404