from dataclasses import dataclass, field
from datetime import datetime

from app.domain.entities.actor import utcnow

@dataclass(eq=False)
class Tombstone:
    """Rastro de una nota borrada. Hace el borrado idempotente y, en la federación,
    impide que la nota reaparezca si su publicación llega después del borrado."""
    id: str
    author_id: str
    deleted: datetime = field(default_factory=utcnow)