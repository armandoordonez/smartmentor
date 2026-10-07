"""Interfaz (puerto) del repositorio del log de llamadas al LLM."""

from typing import Protocol

from app.common.repository import CrudRepository
from app.domains.observability.entities import LlmCallLog


class LlmCallLogRepository(CrudRepository[LlmCallLog], Protocol): ...
