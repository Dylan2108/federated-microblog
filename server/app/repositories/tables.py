"""Esquema de la base de datos y mapeo imperativo de las entidades del dominio.

El dominio (app.domain.entities) no importa SQLAlchemy: es esta capa la que lo conoce a él.
El mapeo se hace una vez, al importar este módulo; sólo lo importan los repositorios.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, MetaData, String, Table
from sqlalchemy.orm import registry, relationship
from app.domain.entities import Actor

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

mapper_registry = registry(metadata=metadata)
mapper_registry.map_imperatively(Actor, actors)