from dataclasses import dataclass, field
from datetime import datetime, timezone

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def base_url(domain: str) -> str:
    """URL con la que se alcanza al servidor `domain` en la red de Docker. Prefijo de todos sus ids."""
    return f"http://{domain}:8000"

@dataclass(eq=False)
class Actor:
    """Un usuario, local a este servidor o cacheado desde uno remoto."""
    id: str
    username: str
    domain: str
    is_local: bool = False
    display_name: str = ""
    password_hash: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    locked: bool = False

    @property
    def handle(self) -> str:
        return f"{self.username}@{self.domain}"