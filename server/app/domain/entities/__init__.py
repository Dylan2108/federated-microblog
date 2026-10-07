"""Entidades del dominio: Python puro, sin dependencias de la base de datos.
La persistencia las mapea desde fuera (repositories/tables.py, mapeo imperativo de SQLAlchemy),
así que el dominio no sabe cómo ni dónde se guardan.
"""
from app.domain.entities.actor import Actor, utcnow
from app.domain.entities.note import MAX_NOTE_LENGTH, Note
from app.domain.entities.follow import Follow

__all__ = ["MAX_NOTE_LENGTH","Actor","Follow","Note","utcnow"]