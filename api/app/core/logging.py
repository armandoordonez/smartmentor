"""Logs estructurados en JSON (stdout), con request_id y sin datos personales."""

import json
import logging
from contextvars import ContextVar
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import Settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Atributos extra que se copian al JSON si el registro los trae.
_EXTRA_FIELDS = ("method", "path", "status_code", "duration_ms", "code")


def mask_email(email: str) -> str:
    """j***@dominio.com. Los logs referencian a los usuarios por id; esto es el último recurso."""
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    return f"{local[:1]}***@{domain}"


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str, environment: str, timezone: str) -> None:
        super().__init__()
        self._service = service
        self._environment = environment
        self._tz = ZoneInfo(timezone)

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, self._tz).isoformat(),
            "level": record.levelname,
            "service": self._service,
            "environment": self._environment,
            "request_id": request_id_var.get(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter("smartmentor-api", settings.app_env, settings.app_timezone))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
    # uvicorn tiene su propio access log: se reemplaza por el middleware de la aplicación.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn").handlers = []
    logging.getLogger("uvicorn.error").handlers = []
