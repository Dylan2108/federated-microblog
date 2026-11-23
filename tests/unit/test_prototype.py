"""El servidor en memoria del prototipo (sin Ray): mismo contrato HTTP, estado en `MemoryRepos`."""

import asyncio
import json

from prototype_ray.server import InMemoryServer

run = asyncio.run


def call(server, method, url, body=None, token=None):
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    status, _, raw = run(server.handle(method, url, headers, json.dumps(body).encode() if body else b""))
    return status, json.loads(raw) if raw else None


def login(server, username):
    call(server, "POST", "/api/register", {"username": username, "password": "secreto1"})
    return call(server, "POST", "/api/login", {"username": username, "password": "secreto1"})[1]["token"]


def test_contract_flow_in_memory():
    server = InMemoryServer("server-a")
    assert call(server, "GET", "/health") == (200, {"status": "ok", "domain": "server-a"})
    ana, beto = login(server, "ana"), login(server, "beto")
    assert call(server, "POST", "/api/users/beto/follow", token=ana) == (200, {"state": "accepted"})
    status, note = call(server, "POST", "/api/notes", {"content": "hola"}, token=beto)
    assert status == 201 and note["author"]["handle"] == "beto@server-a"
    assert [n["content"] for n in call(server, "GET", "/api/timelines/home", token=ana)[1]] == ["hola"]
    assert call(server, "GET", "/api/me")[0] == 401


def test_servers_do_not_share_state_and_keep_request_id():
    a, b = InMemoryServer("server-a"), InMemoryServer("server-b")
    login(a, "ana")
    assert call(b, "GET", "/api/users/ana")[0] == 404
    _, headers, _ = run(a.handle("GET", "/health", {"x-request-id": "mi-id"}, b""))
    assert headers["x-request-id"] == "mi-id"