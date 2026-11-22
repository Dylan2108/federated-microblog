from dataclasses import dataclass, field
from datetime import datetime

from app.domain.entities.actor import Actor, utcnow

MAX_NOTE_LENGTH = 500

# Visibilidad de una nota
PUBLIC = "public"
UNLISTED = "unlisted"
FOLLOWERS = "followers"
VISIBILITIES = (PUBLIC, UNLISTED, FOLLOWERS)
@dataclass(eq=False)
class Note:
    """Publicación corta, local o recibida de otro servidor."""
    id: str
    author_id: str
    content: str
    author: Actor
    published: datetime = field(default_factory=utcnow)
    visibility: str = PUBLIC
    updated: datetime | None = None

    def edit(self, content: str, at: datetime) -> bool:
        """Last-writer-wins: aplica la edición sólo si es más reciente que la última conocida.
        Así una edición antigua que llega tarde de otro servidor no pisa a una nueva."""
        if self.updated is not None and at <= self.updated:
            return False
        self.content, self.updated = content, at
        return True