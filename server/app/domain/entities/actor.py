from dataclasses import dataclass, field
from datetime import datetime, timezone

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

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