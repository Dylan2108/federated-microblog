"""Logs estructurados: una línea JSON por evento en la salida estándar. Sólo biblioteca estándar.

Uso desde cualquier capa:
    log = logging.getLogger(__name__)
    log.info("note_created", extra={"note_id": note.id})

Cada línea lleva el `request_id` de la petición en curso (lo fija el middleware de `main.py`), así que una
operación se sigue filtrando por ese id: `docker logs server-a 2>&1 | grep <request_id>`.
"""

import json
import logging
import sys
from contextvars import ContextVar

request_id: ContextVar[str] = ContextVar("request_id", default="-")

# Atributos que trae cualquier LogRecord; el resto vienen de `extra=` y se añaden al JSON.
_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": request_id.get(),
        }
        data.update({k: v for k, v in vars(record).items() if k not in _STANDARD})
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str, ensure_ascii=False)

def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)