"""Puertos: lo que la lógica de negocio necesita del exterior, definido desde el dominio.
"""

from app.domain.ports.actors import ActorRepo
from app.domain.ports.notes import NoteRepo
from app.domain.ports.repos import Repos
from app.domain.ports.follows import FollowRepo
from app.domain.ports.timeline import TimelineRepo
from app.domain.ports.federation import Federation

__all__ = ["ActorRepo","NoteRepo","Repos","FollowRepo","TimelineRepo","Federation"]