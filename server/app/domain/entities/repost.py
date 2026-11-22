from dataclasses import dataclass, field
from datetime import datetime

from app.domain.entities.actor import utcnow

@dataclass(eq=False)
class Repost:
    """Republicación: `actor_id` comparte la nota `note_id` con sus seguidores."""
    actor_id: str
    note_id: str
    published: datetime = field(default_factory=utcnow)