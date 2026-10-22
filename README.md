# federated-microblog

Proyecto de Sistemas Distribuidos: una red social de micropublicaciones federada
entre varios servidores independientes, inspirada en ActivityPub.

## Estado actual

red social funcional *dentro de cada servidor*, todavía sin federación.

- Registro e inicio de sesión.
- Publicaciones de hasta 500 caracteres.
- Seguir y dejar de seguir a usuarios **del mismo servidor**.
- Timeline home: tus notas y las de quien sigues, las más recientes primero.
- Interfaz web con Streamlit que permite elegir en qué servidor trabajar.

Los tres servidores son independientes: un usuario de `server-a` todavía no puede ver ni seguir a uno
de `server-b`

## Requisitos

- Docker y Docker Compose (plugin `docker compose`, v2).
- Python 3.12, solo para ejecutar los tests desde el host.

## Cómo ejecutar

Levantar los tres servidores , sus bases de datos y la interfaz:

```bash
docker compose up -d --build
```

| Servicio   | URL local               | Qué es                                   |
|------------|-------------------------|------------------------------------------|
| ui         | http://localhost:8501   | Interfaz web (Streamlit)                 |
| server-a   | http://localhost:8001   | API; documentación en `/docs`            |
| server-b   | http://localhost:8002   | API; documentación en `/docs`            |
| server-c   | http://localhost:8003   | API; documentación en `/docs`    

Comprobar que cada uno responde:

```bash
curl localhost:8001/health   # {"status":"ok","domain":"server-a"}
curl localhost:8002/health   # {"status":"ok","domain":"server-b"}
curl localhost:8003/health   # {"status":"ok","domain":"server-c"}
```

### Usar la interfaz

1. Abre http://localhost:8501 y elige un servidor en la barra lateral.
2. En **Registrarse**, crea una cuenta; luego entra desde **Iniciar sesión**.
3. **Inicio**: publicar y ver tu timeline home.
4. **Usuarios**: busca a otro usuario *del mismo servidor* por su nombre, síguele y mira sus notas.
5. **Mi perfil**: a quién sigues, quién te sigue y tus publicaciones.

Cada servidor tiene su propia sesión: puedes estar conectado en `server-a` y `server-b` a la vez.

### Usar la API con curl

```bash
# registrarse e iniciar sesión
curl -X POST localhost:8001/api/register -H 'content-type: application/json' \
     -d '{"username":"ana","password":"secreto1","display_name":"Ana"}'
TOKEN=$(curl -s -X POST localhost:8001/api/login -H 'content-type: application/json' \
     -d '{"username":"ana","password":"secreto1"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

# publicar, seguir y ver la timeline
curl -X POST localhost:8001/api/notes -H "authorization: Bearer $TOKEN" \
     -H 'content-type: application/json' -d '{"content":"hola mundo"}'
curl -X POST localhost:8001/api/users/beto/follow -H "authorization: Bearer $TOKEN"
curl localhost:8001/api/timelines/home -H "authorization: Bearer $TOKEN"
```

La lista completa de endpoints está en http://localhost:8001/docs.


### Probar la API con Bruno

En `bruno/` hay una colección de [Bruno](https://www.usebruno.com/) (cliente de API cuyas peticiones se
guardan como ficheros de texto dentro del repositorio).

1. Instala la aplicación de escritorio de Bruno (no es una dependencia del proyecto).
2. *Open Collection* → elige la carpeta `bruno/` del repositorio.
3. Selecciona el entorno **`local`** (arriba a la derecha).
4. Ejecuta en orden: `auth` (registrar, registrar al otro usuario, login, me) → `notes` → `follows` → `timelines`.
   El login guarda el token y el resto de peticiones lo envían solas.

Las variables (`user`, `otherUser`, `password` y las URLs de los tres servidores) se cambian en
`bruno/environments/local.bru`. Si el usuario ya existe, registrar devuelve 409: se puede seguir con el login.

Por terminal, sin la aplicación: `cd bruno && npx @usebruno/cli run --env local`.

Bruno sirve para explorar y hacer demos; los tests de contrato oficiales siguen siendo los de `tests/e2e/`.

### Tests

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

.venv/bin/pytest                          # todos (los e2e necesitan el compose levantado)
.venv/bin/pytest tests/unit               # solo unitarios, sin Docker
.venv/bin/pytest tests/e2e/test_local.py::test_follow_backfills_and_fans_out   # uno concreto
```

Si los servidores no están levantados, los tests e2e se marcan como *skipped* en lugar de fallar.

Ver logs de un servidor:

```bash
docker compose logs -f server-a
```

Parar todo (mantiene los datos en volúmenes):

```bash
docker compose down
```

Parar y borrar también los datos (útil si cambia el esquema de la base de datos):

```bash
docker compose down -v
```
