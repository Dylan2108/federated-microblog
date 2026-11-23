"""Dobles de prueba del puerto Federation."""

import json

from app.domain.ports import ServerUnavailable
from app.repositories.memory import MemoryRepos
from app.services import activities, inbox, users


class RecordingFederation:
    """Implementa el puerto Federation apuntando lo que se entregaría, sin enviar nada."""

    def __init__(self):
        self.sent: list[tuple[str, dict]] = []  # (dominio destino, actividad)

    async def deliver(self, domain: str, activity: dict) -> None:
        self.sent.append((domain, activity))

    async def fetch_actor(self, domain: str, username: str) -> dict | None:
        raise ServerUnavailable(domain)


class Network:
    """Varios servidores en memoria en el mismo proceso, conectados entre sí.

    `deliver` sólo encola (la entrega es asíncrona, como en la realidad); `run()` entrega lo encolado,
    incluidas las actividades que se generen al procesarlo, hasta que no queda nada. Las actividades
    pasan por JSON para comprobar que se pueden serializar y que el receptor no comparte objetos.
    """

    def __init__(self, *domains: str):
        self.nodes = {d: MemoryRepos(d, self) for d in domains}
        self.queue: list[tuple[str, dict]] = []
        self.delivered: list[tuple[str, dict]] = []

    async def deliver(self, domain: str, activity: dict) -> None:
        self.queue.append((domain, json.loads(json.dumps(activity))))

    async def fetch_actor(self, domain: str, username: str) -> dict | None:
        if domain not in self.nodes:
            raise ServerUnavailable(domain)
        actor = await users.get_local(self.nodes[domain], username)
        return actor and activities.actor_to_dict(actor)

    async def run(self) -> None:
        while self.queue:
            domain, activity = self.queue.pop(0)
            self.delivered.append((domain, activity))
            await inbox.receive(self.nodes[domain], activity)
