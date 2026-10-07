"""Casos de uso del log de llamadas al LLM (métricas de costo, latencia y calidad)."""

from app.common.service import CrudService
from app.domains.observability.entities import LlmCallLog


class LlmCallLogService(CrudService[LlmCallLog]):
    resource_name = "LLM call log"
