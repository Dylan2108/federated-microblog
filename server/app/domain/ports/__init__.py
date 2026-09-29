"""Puertos: lo que la lógica de negocio necesita de la persistencia, definido desde el dominio.
"""

from app.domain.ports.actors import ActorRepo

__all__ = ["ActorRepo"]