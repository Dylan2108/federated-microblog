"""Los tests e2e necesitan los servidores levantados: (docs/deploy.md)."""

import uuid
import httpx
import pytest

SERVERS = {"a": "http://localhost:8001", "b": "http://localhost:8002"}

@pytest.fixture(scope="session", autouse=True)
def servers_up():
    try:
        for url in SERVERS.values():
            httpx.get(f"{url}/health", timeout=2).raise_for_status()
    except httpx.HTTPError:
        pytest.skip("Servidores no disponibles: levántalos como indica docs/deploy.md")

class Client:
    """Usuario recién registrado en un servidor, con su token."""

    def __init__(self, server: str):
        self.http = httpx.Client(base_url=f"{SERVERS[server]}/api", timeout=5)
        self.username = f'u{uuid.uuid4().hex[:10]}'
        self.http.post("/register", json={"username": self.username, "password": "secreto1"})
        token = self.http.post("/login", json={"username": self.username, "password": "secreto1"})
        self.http.headers["Authorization"] = f"Bearer {token.json()['token']}"

    def post(self, content: str, visibility: str = "public") -> dict:
        return self.http.post("/notes", json={"content": content, "visibility": visibility}).json()

    def home(self) -> list[str]:
        return [n["content"] for n in self.http.get("/timelines/home").json()]

@pytest.fixture
def user():
    return lambda server="a": Client(server)