"""El actor Ray: un servidor de la red por actor, encontrado por su nombre (el dominio)."""

import ray

from prototype_ray.server import InMemoryServer

# Los actores con nombre sólo se ven dentro de un mismo espacio de nombres del clúster.
NAMESPACE = "fediverse"

# El actor es el servidor en memoria tal cual: Ray le da un proceso propio en algún worker,
# un nombre con el que encontrarlo y el transporte de las llamadas. Como `handle` es `async`,
# es un actor asíncrono: atiende varias llamadas intercaladas en un mismo hilo.
ServerNode = ray.remote(InMemoryServer)


def get_or_create(domain: str):
    """El actor del servidor `domain`; lo crea si aún no existe.

    - `resources={domain: 1}`: sólo puede vivir en el worker que declara ese recurso. Sin esto Ray coloca
      los actores donde quiere (en las pruebas, los tres en el mismo worker) y la caída de un nodo
      tumbaría varios servidores: aquí la colocación afecta al aislamiento de fallos, no al rendimiento.
    - `detached`: sobrevive al proceso que lo creó (el gateway).
    - Sin reinicios automáticos (`max_restarts` por defecto, 0): si muere su worker, el servidor y su
      estado se pierden.
    """
    options = {"name": domain, "lifetime": "detached", "get_if_exists": True, "resources": {domain: 1}}
    return ServerNode.options(**options).remote(domain)
