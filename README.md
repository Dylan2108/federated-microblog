# federated-microblog

Proyecto de Sistemas Distribuidos: una red social de micropublicaciones federada
entre varios servidores independientes, inspirada en ActivityPub.

## Estado actual

tres servidores levantan con Docker Compose, cada uno con
su propia base de datos PostgreSQL, y exponen un endpoint de salud.

## Requisitos

- Docker y Docker Compose (plugin `docker compose`, v2).

## Cómo ejecutar

Levantar los tres servidores y sus bases de datos:

```bash
docker compose up -d --build
```

Servidores expuestos en el host:

| Servidor | URL local             |
| -------- | --------------------- |
| server-a | http://localhost:8001 |
| server-b | http://localhost:8002 |
| server-c | http://localhost:8003 |

Comprobar que cada uno responde:

```bash
curl localhost:8001/health   # {"status":"ok","domain":"server-a"}
curl localhost:8002/health   # {"status":"ok","domain":"server-b"}
curl localhost:8003/health   # {"status":"ok","domain":"server-c"}
```

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
