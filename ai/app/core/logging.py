"""Structured JSON logs on stdout with ``request_id`` and ``job_id`` (plan 5.4.13).

Never log prompts, learner texts, tokens or secrets: only ids, codes and measurements.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import datetime
from zoneinfo import ZoneInfo

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
job_id_var: ContextVar[str | None] = ContextVar("job_id", default=None)

# Extra attributes copied to the JSON line when a record carries them.
_EXTRA_FIELDS = (
    "method",
    "path",
    "status_code",
    "duration_ms",
    "code",
    "job_type",
    "task",
    "prompt_id",
    "model",
    "call_attempt",
    "latency_ms",
    "attempts",
)


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
            "job_id": job_id_var.get(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(
    *, service: str, environment: str, timezone: str, level: str = "INFO"
) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(service, environment, timezone))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # uvicorn has its own access log: the request middleware replaces it.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn").handlers = []
    logging.getLogger("uvicorn.error").handlers = []
    # The provider SDKs log request bodies at DEBUG: keep them quiet.
    for noisy in ("httpx", "httpcore", "google_genai", "google.genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
