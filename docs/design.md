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
│   entities.py   Actor, Note, Follow (dataclasses)                    │
│   ports.py      interfaces de persistencia (Protocol): Repos, ...    │
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
```

Reglas:

- **Las flechas apuntan al dominio.** `domain/` no importa nada del proyecto salvo sí mismo;
  `services/` sólo importa `domain/` y `core/` (config y seguridad, sin dependencias externas).
- **Inversión de dependencias.** Los casos de uso no conocen los repositorios SQL: dependen de
  los puertos de `domain/ports.py`.
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

### 5.Autenticación de usuarios (cliente → servidor)

- Contraseñas con `scrypt` y sal aleatoria (biblioteca estándar).
- Tokens de sesión `usuario:caducidad:firma-HMAC`, sin estado: el servidor no los guarda y los
  valida recalculando la firma con `SECRET_KEY`. Contrapartida: no se pueden revocar antes de caducar.
