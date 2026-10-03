from dataclasses import dataclass, field
from datetime import datetime

from app.domain.entities.actor import Actor, utcnow

MAX_NOTE_LENGTH = 500

@dataclass(eq=False)
class Note:
    """Publicación corta, local o recibida de otro servidor."""
    id: str
    author_id: str
    content: str
    author: Actor
    published: datetime = field(default_factory=utcnow)