"""Composición: construye el servicio del log de llamadas al LLM."""

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.observability.repository_impl import SqlAlchemyLlmCallLogRepository
from app.domains.observability.service import LlmCallLogService


def get_llm_call_log_service(session: SessionDep) -> LlmCallLogService:
    return LlmCallLogService(SqlAlchemyLlmCallLogRepository(session), SqlAlchemyUnitOfWork(session))
