from dataclasses import dataclass, field
from datetime import datetime

from app.domain.entities.actor import utcnow

PENDING = "pending"
ACCEPTED = "accepted"

@dataclass(eq=False)
class Follow:
    """Relación dirigida: follower sigue a followed."""
    follower_id: str
    followed_id: str
    state: str = ACCEPTED
    created_at: datetime = field(default_factory=utcnow)