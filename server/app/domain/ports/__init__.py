"""Puertos: lo que la lógica de negocio necesita de la persistencia, definido desde el dominio.
"""

from app.domain.ports.actors import ActorRepo
from app.domain.ports.notes import NoteRepo
from app.domain.ports.repos import Repos
from app.domain.ports.follows import FollowRepo

__all__ = ["ActorRepo","NoteRepo","Repos","FollowRepo"]