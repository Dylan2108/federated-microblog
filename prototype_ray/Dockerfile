# Nodo del clúster Ray (cabeza o worker, según el comando de `docker run`).
# Contexto de construcción: la raíz del repositorio (necesita server/app y prototype_ray).
FROM python:3.12-slim

WORKDIR /srv

COPY server/requirements.txt server-requirements.txt
COPY prototype_ray/requirements.txt ray-requirements.txt
RUN pip install --no-cache-dir -r server-requirements.txt -r ray-requirements.txt

COPY server/app ./app
COPY prototype_ray ./prototype_ray
ENV PYTHONPATH=/srv
