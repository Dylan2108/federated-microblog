"""Adaptadores de persistencia: implementan los puertos de `app.domain.ports`.

- `sql`: PostgreSQL con SQLAlchemy (versión nativa). Es la única parte que construye consultas.
- `memory`: diccionarios en memoria (tests unitarios y prototipo Ray). No carga SQLAlchemy.

Este `__init__` no importa ninguno de los dos, para que usar uno no arrastre al otro.
"""
