"""Esquema de la base de datos y mapeo imperativo de las entidades del dominio.

El dominio (app.domain.entities) no importa SQLAlchemy: es esta capa la que lo conoce a él.
El mapeo se hace una vez, al importar este módulo; sólo lo importan los repositorios.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, MetaData, String, Table
from sqlalchemy.orm import registry, relationship
from app.domain.entities import Actor, MAX_NOTE_LENGTH, Note, Follow

metadata = MetaData()

actors = Table(
    "actors",
    metadata,
    Column("id", String, primary_key=True),
    Column("username", String, nullable=False, index=True),
    Column("domain", String, nullable=False, index=True),
    Column("is_local", Boolean, nullable=False),
    Column("display_name", String, nullable=False),
    Column("password_hash",String),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

notes = Table(
    "notes",
    metadata,
    Column("id", String, primary_key=True),
    Column("author_id", ForeignKey("actors.id", ondelete="CASCADE"),nullable=False, index=True),
    Column("content", String(MAX_NOTE_LENGTH), nullable=False),
    Column("published", DateTime(timezone=True), nullable=False, index=True)
)

follows = Table(
    "follows",
    metadata,
    Column("follower_id", ForeignKey("actors.id", ondelete="CASCADE"), primary_key=True),
    Column("followed_id", ForeignKey("actors.id", ondelete="CASCADE"), primary_key=True, index=True),
    Column("state", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False)
)

timeline_entries = Table(
    "timeline_entries",
    metadata,
    Column("owner_id", ForeignKey("actors.id", ondelete="CASCADE"), primary_key=True),
    Column("note_id", ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("sort_date", DateTime(timezone=True), nullable=False, index=True),
)

mapper_registry = registry(metadata=metadata)
mapper_registry.map_imperatively(Actor, actors)
mapper_registry.map_imperatively(Note, notes, properties={"author": relationship(Actor, lazy="joined")})
mapper_registry.map_imperatively(Follow, follows)