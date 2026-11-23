"""Gateway HTTP de un servidor: expone el contrato en un puerto y reenvía cada petición a su actor.

No tiene lógica ni estado: si se reinicia, el servidor (el actor) sigue vivo.
"""

import os

import ray
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from prototype_ray.node import NAMESPACE, get_or_create

DOMAIN = os.environ["DOMAIN"]
FORWARDED_HEADERS = ("authorization", "content-type", "x-request-id")

ray.init(address="auto", namespace=NAMESPACE, log_to_driver=False)  # se une al clúster ya arrancado
node = get_or_create(DOMAIN)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)  # /docs lo sirve el actor


@app.api_route("/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
async def forward(request: Request) -> Response:
    url = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    headers = {k: v for k, v in request.headers.items() if k in FORWARDED_HEADERS}
    try:
        # `.remote()` devuelve al instante una referencia (ObjectRef); `await` espera su resultado.
        status, out_headers, body = await node.handle.remote(request.method, url, headers, await request.body())
    except ray.exceptions.RayActorError:
        return JSONResponse({"detail": f"El servidor {DOMAIN} no está disponible"}, status_code=503)
    return Response(body, status, {k: v for k, v in out_headers.items() if k in FORWARDED_HEADERS})
