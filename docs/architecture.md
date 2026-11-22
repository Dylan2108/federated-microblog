# Arquitectura del sistema

Este documento explica, paso a paso, cómo está organizado el sistema y por qué. Describe el
estado actual del código.

## Índice

- [Arquitectura del sistema](#arquitectura-del-sistema)
  - [Índice](#índice)
  - [1 - Un sistema federado](#1---un-sistema-federado)
    - [1.1 Qué hay desplegado](#11-qué-hay-desplegado)
    - [1.2 Qué significa "federado"](#12-qué-significa-federado)
  - [2 - Clean Architecture dentro de cada servidor](#2---clean-architecture-dentro-de-cada-servidor)
    - [2.1 La regla de dependencia](#21-la-regla-de-dependencia)
    - [2.2 La misma idea, dibujada como flujo](#22-la-misma-idea-dibujada-como-flujo)
    - [2.3 Qué importa cada carpeta (estado real)](#23-qué-importa-cada-carpeta-estado-real)
  - [3. Las capas, una a una](#3-las-capas-una-a-una)
    - [3.1 `domain/entities/`: las entidades](#31-domainentities-las-entidades)
    - [3.2 `domain/ports/`: los puertos (interfaces)](#32-domainports-los-puertos-interfaces)
    - [3.3 `services/`: los casos de uso](#33-services-los-casos-de-uso)
    - [3.4 `repositories/`: el adaptador de base de datos](#34-repositories-el-adaptador-de-base-de-datos)
    - [3.5 `api/`: el adaptador HTTP](#35-api-el-adaptador-http)
    - [3.6 `schemas/`: el contrato HTTP](#36-schemas-el-contrato-http)
    - [3.7 `core/`: utilidades transversales](#37-core-utilidades-transversales)
    - [3.8 `main.py`: el arranque](#38-mainpy-el-arranque)
  - [4. Recorrido de una petición, paso a paso](#4-recorrido-de-una-petición-paso-a-paso)
  - [5. Transacciones y sesión de base de datos](#5-transacciones-y-sesión-de-base-de-datos)
  - [6. Decisiones y alternativas descartadas](#6-decisiones-y-alternativas-descartadas)
  - [7. Limitaciones conocidas](#7-limitaciones-conocidas)

## 1 - Un sistema federado

### 1.1 Qué hay desplegado

```
                 ┌──────────────── red de Docker ─────────────────┐
 Streamlit (ui) ─┤                                                 │
  :8501          │   server-a :8001        server-b :8002          │
                 │       │                     │                   │
                 │   postgres-a            postgres-b              │
                 │                                                 │
                 │   server-c :8003                                │
                 │       │                                         │
                 │   postgres-c                                    │
                 └─────────────────────────────────────────────────┘
```

- **Tres servidores** (`server-a`, `server-b`, `server-c`) ejecutan **el mismo código**
  (`server/`). Sólo se diferencian por dos variables de entorno, `DOMAIN` y `DATABASE_URL`,
  que lee `app/core/config.py`.
- **Cada servidor tiene su propia base de datos PostgreSQL.** No hay base de datos compartida:
  `server-a` no puede leer las tablas de `server-b`.
- **La interfaz** (Streamlit) no es parte de ningún servidor: es un cliente que puede
  conectarse a cualquiera de los tres (selector en la barra lateral).
- Todo se levanta con `docker compose up -d --build` (ver `docker-compose.yml`).

### 1.2 Qué significa "federado"

- **No hay servidor central ni maestro.** Todos son iguales (*peers*).
- **Cada servidor es dueño de sus usuarios.** `ana` registrada en `server-a` es
  `@ana@server-a`
- **Los servidores sólo se comunican por HTTP**, mediante un protocolo común inspirado en
  ActivityPub . Es el mismo modelo que el correo electrónico o Mastodon.
- **Consecuencia:** si un servidor cae, los demás siguen funcionando para sus propios
  usuarios. El precio es que las vistas entre servidores pueden estar temporalmente
  desincronizadas

> Estado actual: los tres servidores ya son independientes, pero todavía **no
> se comunican entre sí**.

---

## 2 - Clean Architecture dentro de cada servidor

### 2.1 La regla de dependencia

Clean Architecture tiene una sola regla fundamental:

> **Las dependencias del código apuntan hacia dentro, hacia el dominio.** Lo de dentro no
> sabe nada de lo de fuera.

"Dentro" es lo más estable y valioso: las entidades y las reglas de negocio. "Fuera" es lo
más cambiante y técnico: el framework web, la base de datos, el protocolo HTTP.

```
            ┌───────────────────────────────────────────────┐
            │  ADAPTADORES (fuera)                          │
            │  api/  ·  repositories/  ·  core/db           │
            │     ┌─────────────────────────────────┐       │
            │     │  CASOS DE USO                   │       │
            │     │  services/                      │       │
            │     │     ┌───────────────────┐       │       │
            │     │     │  DOMINIO          │       │       │
            │     │     │  domain/          │       │       │
            │     │     │  entities · ports │       │       │
            │     │     └───────────────────┘       │       │
            │     └─────────────────────────────────┘       │
            └───────────────────────────────────────────────┘
                    todas las flechas de import → hacia el centro
```

### 2.2 La misma idea, dibujada como flujo

```
        Streamlit (usuario)         
               │ HTTP                     
               ▼                          
┌──────────────────────────────────────────────────────────────────────┐
│ ADAPTADORES DE ENTRADA      api/  ·  					               │
│   FastAPI: validan (schemas/), llaman a un caso de uso, responden    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ llaman a
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ CASOS DE USO                services/                                │
│   users · follows · notes · timeline        (sin sqlalchemy/fastapi) │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ usan
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ DOMINIO                     domain/                    Python puro   │
│     entities/     actor · note · follow · repost · tombstone         │
│   ports/        actors · notes · follows · reposts · timeline · repos│       │
└───────────────────────────────▲──────────────────────────────────────┘
                                │ implementan los puertos
                                │ y mapean las entidades
┌───────────────────────────────┴──────────────────────────────────────┐
│ ADAPTADORES DE SALIDA       repositories/                            │
│   tables.py (esquema + mapeo) · actors · notes · follows · timeline  │
└───────────────────────────────┬──────────────────────────────────────┘
                                ▼
                  core/db (sesión)  →  PostgreSQL
```

Fíjate en la flecha entre `domain/` y `repositories/`: **apunta hacia arriba**. La base de
datos depende del dominio, no al revés. Eso es la *inversión de dependencias*, y es lo que
diferencia esta arquitectura de una arquitectura en capas clásica, donde todo depende de la
base de datos.

### 2.3 Qué importa cada carpeta (estado real)

| Carpeta | Importa de | Nunca importa |
|---|---|---|
| `domain/` | sólo `domain/` | nada más del proyecto, ni `sqlalchemy`, ni `fastapi` |
| `services/` | `domain/`, `core/config`, `core/security` | `api/`, `repositories/`, `sqlalchemy`, `fastapi` |
| `repositories/` | `domain/`, `sqlalchemy` | `services/`, `api/` |
| `schemas/` | `domain/` (sólo `MAX_NOTE_LENGTH`), `pydantic` | `services/`, `repositories/` |
| `api/` | `services/`, `domain/`, `schemas/`, `core/`; sólo `deps.py` importa `repositories/` | — (es la capa más externa) |

Los routers tipan `repos` con el puerto `domain.ports.Repos`; sólo `api/deps.py` (la raíz de
composición) conoce la implementación concreta de `repositories/`.

---

## 3. Las capas, una a una

### 3.1 `domain/entities/`: las entidades

Un fichero por entidad: `actor.py`, `note.py`, `follow.py`, `repost.py`, `tombstone.py`. Son **dataclasses de Python
puro**:

```python
@dataclass(eq=False)
class Actor:
    id: str                 # URL del actor, p. ej. http://server-a:8000/users/ana
    username: str
    domain: str
    is_local: bool = False
    display_name: str = ""
    password_hash: str | None = None
    created_at: datetime = field(default_factory=utcnow)
```

- **No saben que existe una base de datos.** No heredan de nada de SQLAlchemy ni tienen
  `__tablename__` ni `Column`.
- `eq=False`: dos objetos son iguales sólo si son el mismo objeto (identidad), que es lo que
  espera el ORM. Sin esto, la dataclass compararía campo a campo.
- Los **ids son URLs** para que sean únicos en toda la federación: `@ana@server-a` y
  `@ana@server-b` tienen ids distintos aunque el nombre coincida.
- `Note.author` es obligatorio al construir una nota: asignar `None` a una relación del ORM
  haría que al guardar se vaciase `author_id`.
- `entities/__init__.py` reexporta todo, así que se importa como
  `from app.domain.entities import Actor, Note`.

### 3.2 `domain/ports/`: los puertos (interfaces)

Un fichero por puerto: `actors.py`, `notes.py`, `follows.py`, `timeline.py` y `repos.py`.
Cada uno es un `Protocol`: describe **qué necesita** la lógica de negocio de la
persistencia, sin decir **cómo** se hace.

```python
class FollowRepo(Protocol):
    async def exists(self, follower_id: str, followed_id: str) -> bool: ...
    def add(self, follower_id: str, followed_id: str) -> None: ...
    async def followers(self, actor_id: str) -> list[Actor]: ...
    ...

class Repos(Protocol):          # lo que recibe cada caso de uso
    actors: ActorRepo
    notes: NoteRepo
    follows: FollowRepo
    timeline: TimelineRepo
    async def commit(self) -> None: ...
```

- Los puertos se definen **en el dominio**, no en la capa de base de datos. Es la clave de
  la inversión de dependencias: el dominio dicta el contrato y la base de datos lo cumple.
  - Hay **dos implementaciones**: `app/repositories/sql.py` (PostgreSQL) y `app/repositories/memory.py`
- `Protocol` usa *tipado estructural*: una clase cumple el puerto si tiene los mismos
  métodos, sin necesidad de heredar de él.

### 3.3 `services/`: los casos de uso

Un fichero por área: `users.py`, `notes.py`, `follows.py`, `timeline.py`. Contienen las
**reglas de negocio**:

| Service                | Reglas que implementa                                                                                                             |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `users.register`     | nombre único; hash de la contraseña; nombre visible por defecto = usuario                                                       |
| `users.authenticate` | devuelve el actor sólo si la contraseña es correcta                                                                             |
| `follows.follow`     | no puedes seguirte a ti mismo; seguir dos veces no hace nada (idempotente); trae las últimas 20 notas del seguido (*backfill*) |
| `follows.unfollow`   | borra la relación y retira de tu home las notas del que dejas de seguir                                                          |
| `notes.create`       | crea la nota y la reparte a la home del autor y de sus seguidores **locales** (*fan-out*)                                 |
| `timeline.home`      | tu timeline, de más reciente a más antigua                                                                                      |

Cada función recibe `repos` (tipado con el puerto `domain.ports.Repos`) como primer
argumento. Nunca crean sesiones, ni escriben SQL, ni saben de HTTP.

### 3.4 `repositories/`: el adaptador de base de datos

Es la **única carpeta que contiene consultas SQL** (vía SQLAlchemy).

**`tables.py`: el esquema y el mapeo imperativo.** Define las tablas con `Table(...)` y les
asocia las entidades del dominio:

```python
actors = Table("actors", metadata, Column("id", String, primary_key=True), ...)

mapper_registry.map_imperatively(Actor, actors)
mapper_registry.map_imperatively(Note, notes, properties={"author": relationship(Actor, lazy="joined")})
mapper_registry.map_imperatively(Follow, follows)
```

El *mapeo imperativo* conecta una clase ya existente con una tabla **desde fuera**, sin que
la clase lo sepa.

`timeline_entries` es sólo una tabla, sin entidad: es un detalle de persistencia del fan-out
(una tabla de lectura), no un concepto del negocio.

**Un repositorio por agregado** (`actors.py`, `notes.py`, `follows.py`, `timeline.py`):
clases que reciben la sesión y exponen los métodos del puerto correspondiente.

**`sql.py`: la clase `SqlRepos`.** Agrupa los cuatro repositorios sobre **una misma
sesión** y expone `commit()`. Es la implementación SQL del puerto `Repos`.

**`memory.py`: la clase `MemoryRepos`.** La misma interfaz con diccionarios en memoria. La usan los
tests unitarios y el prototipo Ray. `repositories/__init__.py` está vacío a propósito: así importar
`memory` no carga SQLAlchemy ni activa el mapeo de `tables.py`.

### 3.5 `api/`: el adaptador HTTP

- **Routers** (`auth.py`, `users.py`, `notes.py`, `timelines.py`): un endpoint por
  operación. Son **finos**: validan la entrada, llaman a un service y devuelven la respuesta.
  No contienen reglas de negocio.
- **`deps.py`: la raíz de composición.** Es el único sitio que decide qué implementación
  concreta se usa:
  - `get_repos`: abre una sesión de PostgreSQL por petición (`core/db.get_db`) y crea con
    ella el `SqlRepos` (`repositories/sql.py`).
  - `get_current_user`: lee la cabecera `Authorization: Bearer <token>`, verifica el token y
    devuelve el `Actor` autenticado, o responde 401. Está aquí (y no en `services/`) porque
    es una cuestión de HTTP; y aquí (y no en `auth.py`) porque la usan casi todos los routers.

### 3.6 `schemas/`: el contrato HTTP

Modelos de Pydantic que definen **el formato del JSON** que entra y sale:

- **Entrada (`RegisterIn`, `LoginIn`, `NoteIn`)**: FastAPI valida el cuerpo de la petición y
  responde **422** automáticamente si no cumple (usuario con mayúsculas, nota vacía o de más
  de 500 caracteres…). Los services reciben siempre datos válidos.
- **Salida (`UserOut`, `NoteOut`, `TokenOut`)**: deciden qué campos se devuelven. `UserOut`
  **no incluye `password_hash`**: sin este schema, el hash acabaría en las respuestas.

Las entidades describen el dato **dentro** del sistema; los schemas, cómo se **expone**
fuera. Separarlos permite cambiar uno sin romper el otro.

### 3.7 `core/`: utilidades transversales

- `config.py`: variables de entorno (`DOMAIN`, `DATABASE_URL`, `SECRET_KEY`…).
- `db.py`: el motor de base de datos y `get_db`, que abre y cierra una sesión por petición.
- `security.py`: hash de contraseñas con `scrypt` y tokens de sesión firmados con HMAC. Sólo
  usa la biblioteca estándar.

### 3.8 `main.py`: el arranque

Crea la aplicación FastAPI, registra los routers y, al arrancar, crea las tablas
(`metadata.create_all`, a partir de `repositories/tables.py`) si no existen.

---

## 4. Recorrido de una petición, paso a paso

Ejemplo: `ana` (en `server-a`) publica "hola". La interfaz envía:

```http
POST /api/notes
Authorization: Bearer <token de ana>
Content-Type: application/json

{"content": "hola"}
```

**Paso 1: FastAPI recibe la petición** y encuentra el endpoint en `api/notes.py`:

```python
@router.post("", response_model=NoteOut, status_code=201)
async def create_note(body: NoteIn,
                      user: Actor = Depends(get_current_user),
                      repos: Repos = Depends(get_repos)):
    return await notes.create(repos, user, body.content)
```

**Paso 2: se valida el cuerpo** contra `schemas/client.NoteIn`. Si `content` estuviera vacío
o tuviera más de 500 caracteres, se respondería 422 aquí mismo.

**Paso 3: se resuelven las dependencias** de `api/deps.py`:

1. `get_db` abre una sesión con `postgres-a`.
2. `get_repos` construye `Repos(sesión)`.
3. `get_current_user` verifica el token (`core/security.read_token`) y busca a `ana` con
   `services/users.get_local(repos, "ana")`. Si el token es inválido, responde 401 y el
   endpoint no llega a ejecutarse.

FastAPI resuelve `get_repos` **una sola vez por petición**: el endpoint y `get_current_user`
reciben el mismo `Repos`, con la misma sesión.

**Paso 4: el router llama al caso de uso** `services/notes.create(repos, ana, "hola")`:

```python
note = Note(id=f"{settings.base_url}/notes/{uuid4()}", author=author,
            author_id=author.id, content=content)
await repos.notes.add(note)            # INSERT en notes (+ flush)
await timeline.fan_out(repos, note)    # reparto a las homes
await repos.commit()                   # un único COMMIT
```

**Paso 5: fan-out** (`services/timeline.fan_out`): pide los seguidores locales de `ana`
(`repos.follows.local_follower_ids`) e inserta una fila en `timeline_entries` para `ana` y
para cada uno de ellos (`repos.timeline.add`).

**Paso 6: los repositorios traducen a SQL** (`repositories/notes.py`,
`repositories/follows.py`, `repositories/timeline.py`). Gracias al mapeo de `tables.py`,
SQLAlchemy sabe convertir el objeto `Note` en una fila de `notes`.

**Paso 7: commit.** `repos.commit()` confirma la transacción: la nota y todas las entradas de
timeline se guardan **juntas o ninguna**.

**Paso 8: la respuesta.** El service devuelve la entidad `Note`; FastAPI la convierte en
JSON con `schemas/client.NoteOut` y responde **201**:

```json
{"id": "http://server-a:8000/notes/…", "content": "hola",
 "author": {"id": "http://server-a:8000/users/ana", "username": "ana", …},
 "published": "2026-09-26T…"}
```

**Paso 9: se cierra la sesión** (`get_db` sale de su bloque `async with`).

Resumen de quién hace qué:

| Paso | Dónde                            | Responsabilidad                  |
| ---- | --------------------------------- | -------------------------------- |
| 1-2  | `api/notes.py`, `schemas/`    | Recibir y validar HTTP           |
| 3    | `api/deps.py`, `core/`        | Autenticar y preparar la sesión |
| 4-5  | `services/`                     | Reglas de negocio                |
| 6    | `repositories/`                 | Traducir a SQL                   |
| 7-9  | `repositories/`, `core/db.py` | Persistir y cerrar               |

---

## 5. Transacciones y sesión de base de datos

- **Una sesión por petición HTTP**, abierta por `core/db.get_db` y cerrada al terminar.
- **Un único `commit()` por acción de negocio.** Las funciones auxiliares de
  `services/timeline.py` (`fan_out`, `backfill`, `remove_author`) **nunca hacen commit**: lo
  hace el service que las llama (`notes.create`, `follows.follow`, `follows.unfollow`) al
  final. Así una acción completa es atómica: o se aplica entera o no se aplica.
- `NoteRepo.add` hace `flush()` (envía el `INSERT` sin confirmar) porque `timeline_entries`
  tiene una clave foránea hacia `notes`: la nota debe existir en la transacción antes de
  referenciarla.
- `expire_on_commit=False` (en `core/db.py`) permite seguir usando los objetos devueltos
  después del commit, para construir la respuesta.

---

## 6. Decisiones y alternativas descartadas

| Decisión                                   | Alternativa descartada                                            | Motivo                                                                                  |
| ------------------------------------------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Repositorios entre services y base de datos | Services con consultas SQLAlchemy directas                        | Acoplaba la lógica al ORM y obligaba a tener Postgres para probar cualquier regla      |
| Entidades dataclass + mapeo imperativo      | Entidades declarativas de SQLAlchemy (`class Actor(Base)`)      | El dominio dependía del ORM                                                            |
| Mapeo imperativo                            | Entidades puras + modelos ORM separados + traductores entre ambos | Duplicaba cada entidad y exigía código de conversión                                 |
| Puertos con `Protocol`                    | Clases base abstractas (`ABC`)                                  | `Protocol` no obliga a heredar: los repositorios SQL cumplen el contrato por su forma |
| Regla de dependencia por dirección         | Capas estrictas (sólo la inmediata)                              | Obligaría a reenviar o duplicar entidades sin beneficio                                |
| Fan-out en escritura (`timeline_entries`) | Fan-out en lectura (calcular la home en cada petición)           | Leer la timeline es una sola consulta indexada; el coste se paga al publicar            |
| Tokens de sesión firmados sin estado       | Sesiones guardadas en la base de datos                            | Sin tablas extra; a cambio no se pueden revocar antes de caducar                        |

---

## 7. Limitaciones conocidas

1. **El contrato de los puertos no se verifica automáticamente.** Python no comprueba las
   anotaciones al ejecutar y el proyecto no usa un verificador de tipos (`mypy`/`pyright`).
   Si el repositorio SQL  deja de cumplir un puerto (falta un método, cambia su
   firma, `async` en uno y no en otro), el error sólo aparece al ejecutar ese camino: un 500
   en la API o, en el peor caso (un `async` sin `await`), un fallo silencioso. Mitigación
   posible: un test de contrato que compare, con `inspect`, los métodos de cada `Protocol`
   con los del repositorio SQL y el fake.
2. **Sin migraciones.** Las tablas se crean al arrancar; un cambio de esquema exige
   `docker compose down -v`, que borra los datos.
