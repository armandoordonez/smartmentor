"""Repositorio SQLAlchemy del log de llamadas al LLM."""

from typing import ClassVar

from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.observability.entities import LlmCallLog
from app.domains.observability.models import LlmCallLogModel


class SqlAlchemyLlmCallLogRepository(SqlAlchemyCrudRepository[LlmCallLogModel, LlmCallLog]):
    model = LlmCallLogModel
    entity = LlmCallLog
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "llm_call_logs_enrollment_id_fk": (
            "ENROLLMENT_NOT_FOUND",
            "The enrollment does not exist.",
        ),
        "llm_call_logs_status_ck": ("INVALID_LLM_CALL_STATUS", "status must be success or error."),
    }
