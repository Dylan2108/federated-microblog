# Despliegue a mano con `docker run`

El sistema se despliega con comandos de Docker, sin Compose ni otro orquestador: cada decisión de despliegue
(red, nombres, puertos, volúmenes, orden de arranque) se toma explícitamente en un comando. Hay **un
Dockerfile por tipo de nodo** y cada nodo es un `docker run`.

| Tipo de nodo       | Imagen                                        | Dockerfile            | Instancias                                     |
| ------------------ | --------------------------------------------- | --------------------- | ---------------------------------------------- |
| Servidor de la red | `social-server`                             | `server/Dockerfile` | `server-a`, `server-b`, `server-c`       |
| Base de datos      | `postgres:16-alpine` (oficial, sin cambios) | —                    | `postgres-a`, `postgres-b`, `postgres-c` |
| Interfaz           | `social-ui`                                 | `ui/Dockerfile`     | `ui`                                         |

Todos los comandos se ejecutan desde la raíz del repositorio.

---

## 1. Construir las imágenes

Una imagen por tipo de nodo. Los tres servidores salen de la **misma** imagen: sólo cambian sus variables de
entorno.

```bash
docker build -t social-server ./server
docker build -t social-ui ./ui
docker pull postgres:16-alpine
```

## 2. Crear la red

```bash
docker network create fediverse
```

Una red *bridge* definida por el usuario. Además de aislar el sistema, Docker le da un **DNS interno**: dentro
de la red, cada contenedor se alcanza por su `--name`. Así `server-a` encuentra a `postgres-a` y a `server-b`
sin conocer sus direcciones IP. (La red `bridge` por defecto no tiene este DNS.)

## 3. Bases de datos

Una por servidor; no se comparten. Los datos van en un volumen con nombre, que sobrevive a borrar el
contenedor.

```bash
docker volume create postgres-a-data
docker run -d --name postgres-a --network fediverse \
  -e POSTGRES_DB=social -e POSTGRES_USER=social -e POSTGRES_PASSWORD=social \
  -v postgres-a-data:/var/lib/postgresql/data \
  postgres:16-alpine
```

| Opción                                         | Para qué                                                                                       |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `-d`                                          | En segundo plano.                                                                               |
| `--name postgres-a`                           | Nombre del contenedor **y** su nombre en el DNS de la red.                                |
| `--network fediverse`                         | Lo conecta a la red del sistema.                                                                |
| `-e …`                                       | Base de datos, usuario y contraseña que crea la imagen al iniciar por primera vez.             |
| `-v postgres-a-data:/var/lib/postgresql/data` | Monta el volumen donde PostgreSQL guarda los datos.                                             |
| (sin `-p`)                                    | La base de datos **no se publica** en el host: sólo la alcanza su servidor desde la red. |

Las otras dos, igual con su letra:

```bash
docker volume create postgres-b-data
docker run -d --name postgres-b --network fediverse \
  -e POSTGRES_DB=social -e POSTGRES_USER=social -e POSTGRES_PASSWORD=social \
  -v postgres-b-data:/var/lib/postgresql/data \
  postgres:16-alpine

docker volume create postgres-c-data
docker run -d --name postgres-c --network fediverse \
  -e POSTGRES_DB=social -e POSTGRES_USER=social -e POSTGRES_PASSWORD=social \
  -v postgres-c-data:/var/lib/postgresql/data \
  postgres:16-alpine
```

Comprobar que aceptan conexiones (tarda unos segundos la primera vez):

```bash
docker exec postgres-a pg_isready -U social   # "accepting connections"
```

## 4. Servidores

```bash
docker run -d --name server-a --network fediverse -p 8001:8000 \
  -e DOMAIN=server-a \
  -e DATABASE_URL=postgresql+asyncpg://social:social@postgres-a:5432/social \
  social-server
```

| Opción                             | Para qué                                                                                                                                                                                  |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--name server-a`                 | Su nombre en el DNS de la red: así lo alcanzan los otros servidores.                                                                                                                      |
| `-p 8001:8000`                    | Publica el puerto 8000 del contenedor en el 8001 del host (clientes, tests, Bruno).                                                                                                        |
| `-e DOMAIN=server-a`              | Identidad del servidor. **Debe coincidir con `--name`**: los ids de usuarios y notas son URLs `http://<DOMAIN>:8000/...`, y otros servidores las resuelven con el DNS de la red. |
| `-e DATABASE_URL=…@postgres-a…` | Su base de datos, por el nombre del contenedor.                                                                                                                                            |

```bash
docker run -d --name server-b --network fediverse -p 8002:8000 \
  -e DOMAIN=server-b \
  -e DATABASE_URL=postgresql+asyncpg://social:social@postgres-b:5432/social \
  social-server

docker run -d --name server-c --network fediverse -p 8003:8000 \
  -e DOMAIN=server-c \
  -e DATABASE_URL=postgresql+asyncpg://social:social@postgres-c:5432/social \
  social-server
```

**Orden de arranque.** No hay nada que obligue a lanzar la base de datos antes que su servidor. El servidor
reintenta conectarse durante 30 segundos al arrancar (`server/app/main.py::create_tables`); mientras tanto
registra `database_unavailable` en sus logs. Si en ese tiempo no hay base de datos, el proceso termina.

## 5. Interfaz

```bash
docker run -d --name ui --network fediverse -p 8501:8501 \
  -e SERVERS=server-a=http://server-a:8000,server-b=http://server-b:8000,server-c=http://server-c:8000 \
  social-ui
```

La UI habla con los servidores **por la red** (`http://server-a:8000`), no por los puertos del host.

## 6. Comprobar

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
curl localhost:8001/health   # {"status":"ok","domain":"server-a"}
curl localhost:8002/health
curl localhost:8003/health
docker network inspect fediverse --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}{{"\n"}}{{end}}'
.venv/bin/pytest -q          # unitarios + e2e
```

Interfaz en http://localhost:8501; documentación de la API en `http://localhost:800X/docs`.

---

## Operación diaria

**Logs** (JSON, una línea por evento; se filtra por `request_id` o `activity_id`):

```bash
docker logs -f server-a
docker logs server-a 2>&1 | grep <request_id>
```

**Actualizar el código** de los servidores (los datos se conservan en los volúmenes):

```bash
docker build -t social-server ./server
docker rm -f server-a server-b server-c
# y volver a lanzar los tres `docker run` del paso 4
```

Para la interfaz, lo mismo con `docker build -t social-ui ./ui`, `docker rm -f ui` y el paso 5.

**Consultar una base de datos:**

```bash
docker exec -it postgres-a psql -U social -d social -c '\dt'
```

**Borrar los datos.** Hace falta cuando cambia el esquema, porque no hay migraciones (las tablas se crean al
arrancar): parar los servidores y las bases de datos, borrar los volúmenes y repetir los pasos 3 y 4.

```bash
docker rm -f server-a server-b server-c postgres-a postgres-b postgres-c
docker volume rm postgres-a-data postgres-b-data postgres-c-data
```

**Parar todo** (los volúmenes y las imágenes se conservan):

```bash
docker rm -f ui server-a server-b server-c postgres-a postgres-b postgres-c
```

**Desmontarlo del todo:** lo anterior, más `docker volume rm …` y `docker network rm fediverse`.

---
