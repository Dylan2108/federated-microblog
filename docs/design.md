# Diseño de la red federada de micropublicaciones

## 1. Idea general

Cada servidor es una instancia independiente: su propio proceso, su propia base de
datos y su propio dominio (`server-a`, `server-b`, `server-c`). El mismo código corre en los tres; sólo cambian
las variables de entorno (`DOMAIN`, `DATABASE_URL`).

## 2. Arquitectura interna de cada servidor (Clean Architecture)

Cada servidor sigue la **regla de dependencia** de Clean Architecture: el código depende siempre
hacia el centro (el dominio), y el dominio no conoce la base de datos, el framework web ni HTTP.

```
        Streamlit (usuario)
               │ HTTP                      
               ▼                            
┌──────────────────────────────────────────────────────────────────────┐
│ ADAPTADORES DE ENTRADA      api/  ·   						       │
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
│   entities/     actor · note · follow · repost · tombstone           │
│   ports/ actors · notes · follows · reposts · timeline · repos       │
└───────────────────────────────▲──────────────────────────────────────┘
                                │ implementan los puertos
                                │ y mapean las entidades
┌───────────────────────────────┴──────────────────────────────────────┐
│ ADAPTADORES DE SALIDA       repositories/                            │
│   tables.py     esquema + mapeo imperativo (map_imperatively)        │
│   actors · notes · follows · timeline     (únicas consultas SQL)     │
└───────────────────────────────┬──────────────────────────────────────┘
                                ▼
            core/db (sesión)  →  PostgreSQL (propia de este servidor)

  api/deps.py es la "raíz de composición": crea el Repos de SQL y se lo pasa a los casos de uso.
    En los tests unitarios se les pasa repositories/memory.py (en memoria) en su lugar.
```

Reglas:

- **Las flechas apuntan al dominio.** `domain/` no importa nada del proyecto salvo sí mismo;
  `services/` sólo importa `domain/` y `core/` (config y seguridad, sin dependencias externas).
- **Inversión de dependencias.** Los casos de uso no conocen los repositorios SQL: dependen de
  los puertos de `domain/ports.py`.  Hay dos implementaciones, `repositories/` (PostgreSQL) y  `repositories/memory.py` (memoria), y cada petición HTTP recibe la primera desde `api/deps.py`.
- **Entidades independientes del ORM.** `Actor`, `Note` y `Follow` son dataclasses. El esquema y
  su correspondencia con las entidades viven en `repositories/tables.py` mediante el *mapeo
  imperativo* de SQLAlchemy . Así una tabla puede cambiar sin tocar el dominio. Matiz: SQLAlchemy instrumenta las
  clases en tiempo de ejecución cuando se importa `tables.py`; el *código* del dominio no depende
  del ORM, pero en el proceso del servidor sus clases sí quedan mapeadas.
- `timeline_entries` no tiene entidad: es una tabla de lectura del fan-out, un detalle de
  persistencia que sólo existe en `repositories/`.
- Los adaptadores de entrada no llevan lógica: validan, llaman a un caso de uso y responden.

## 3. Identidad

- Identificador: `@usuario@dominio`.

## 4. Timelines

Timelines por fan-out en escritura: al llegar una publicación se inserta en la
timeline de cada seguidor local que tenga permiso de verla.

### 4.1 Timeline home

La tabla `timeline_entries(owner_id, note_id, sort_date)` guarda qué notas ve cada usuario local.

| Evento                 | Efecto en `timeline_entries`                                        |
| ---------------------- | --------------------------------------------------------------------- |
| A publica una nota     | Se inserta para A y para cada seguidor local de A                     |
| A empieza a seguir a B | Se insertan en la home de A las últimas 20 notas de B (*backfill*) |
| A deja de seguir a B   | Se borran de la home de A todas las notas de B                        |

- Orden: `sort_date` = fecha de publicación de la nota, de más reciente a más antigua.
- Las inserciones usan `ON CONFLICT DO NOTHING`: repetir un evento no duplica entradas (idempotencia).
- La publicación y su fan-out van en la **misma transacción**: o aparece en todas las homes o en ninguna.
- Coste: publicar es O(seguidores locales) escrituras; leer la home es una única consulta indexada.
  La alternativa, *fan-out en lectura*, invierte el coste: publicar es barato, pero leer la home
  requiere juntar las notas de todas las cuentas seguidas en cada petición.

### 4.2 Republicaciones

- Una republicación (`Repost`: quién, qué nota y cuándo) se guarda en la tabla `reposts` y se reparte como
  una nota: a la home de quien republica y a las de sus seguidores locales. La entrada de timeline guarda
  `reposted_by` y se ordena por la fecha de la republicación.
- **Una nota, una entrada por home:** la clave de `timeline_entries` es `(owner_id, note_id)`. Si la nota
  llega por otro camino, sólo se sustituye la entrada cuando la nueva es más reciente
  (`ON CONFLICT DO UPDATE … WHERE sort_date < excluded.sort_date`). Así una home muestra la republicación
  más reciente y repetir un reparto no cambia nada (idempotente).
- **Deshacer** borra las entradas que llegaron por esa republicación y vuelve a repartir la nota por los
  caminos que siguen en pie (el autor y las demás republicaciones): quien también seguía al autor la
  conserva. Cuesta O(republicaciones × seguidores), aceptable para el tamaño del proyecto.
- Sólo se republican notas `public` y `unlisted` (`privacy.can_repost`): republicar una `followers` la
  enseñaría a seguidores de otra cuenta.
- Límite conocido: al dejar de seguir a alguien salen también sus republicaciones, aunque alguna nota
  republicada llegase además por otra cuenta seguida.

### 5.Autenticación de usuarios (cliente → servidor)

- Contraseñas con `scrypt` y sal aleatoria (biblioteca estándar).
- Tokens de sesión `usuario:caducidad:firma-HMAC`, sin estado: el servidor no los guarda y los
  valida recalculando la firma con `SECRET_KEY`. Contrapartida: no se pueden revocar antes de caducar.

## 6. Privacidad

Cada nota tiene una visibilidad: `public`, `unlisted` o `followers`

- **Un único punto de decisión:** `services/privacy.py`. `visibilities_for(viewer, autor)` devuelve
  las visibilidades que un lector puede ver de un autor (todas si es el autor o un seguidor
  aceptado; `public` y `unlisted` en otro caso) y `can_see` lo aplica a una nota. Las timelines
  local y federada usan `PUBLIC_TIMELINES` (sólo `public`).
- **No revelar existencia:** pedir una nota que no se puede ver devuelve 404, igual que si no
  existiera.
- **La home no necesita filtro:** el fan-out sólo reparte al autor y a sus seguidores aceptados,
  que pueden ver cualquier visibilidad.
- **Límite:** un servidor remoto que reciba una nota `followers` podría mostrarla a quien no
  debe; la privacidad entre servidores depende de confiar en ellos.

### 6.1 Cuentas privadas

- `Actor.locked` marca una cuenta privada. Seguirla crea un `Follow` en estado `pending`; sólo uno
  `accepted` cuenta como seguidor (`followers`, `local_follower_ids`, `is_follower`), así que un pendiente
  no recibe nada en su home ni ve notas `followers`. La regla de privacidad no cambia: ya preguntaba por
  seguidores aceptados.
- Aceptar pasa el `Follow` a `accepted` y hace el *backfill* en la home del nuevo seguidor; rechazar lo
  borra. Ambas son idempotentes.
- Pasar la cuenta a pública acepta todas las solicitudes pendientes en la misma transacción.
- En la federación un seguimiento remoto también empieza `pending` hasta que llega el `Accept`.

Bloqueos: fuera de alcance (opcional).

## 7. Ediciones, eliminaciones y desconexiones

- **Edición:** cambia el contenido y fija `updated`. La regla *last-writer-wins* está en la
  entidad (`Note.edit`): una edición sólo se aplica si es más reciente que la última conocida, así una
  edición antigua que llegue tarde de otro servidor no pisa a una nueva. Depende de los relojes:
  dos ediciones casi simultáneas desde servidores con relojes desfasados podrían resolverse al revés, un
  riesgo aceptable porque sólo el servidor del autor edita.
- **Borrado:** se borra la nota (la base de datos borra en cascada sus republicaciones y entradas de
  timeline) y se guarda un `Tombstone` (id, autor, fecha). El tombstone hace el borrado idempotente
  (borrar otra vez una nota propia devuelve 204) y, en la federación, permitirá rechazar un `Create` que
  llegue después de su `Delete`.
- Editar o borrar una nota que el usuario no puede ver devuelve 404, no 403: no se revela que existe.
- Un servidor caído recibe lo pendiente al volver (consistencia eventual) gracias a la cola de reintentos.
