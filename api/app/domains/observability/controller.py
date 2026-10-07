"""Endpoints de observabilidad: /llm-call-logs."""

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.auth.dependencies import require_roles
from app.auth.policies import ADMIN
from app.common.controller import build_crud_router
from app.domains.observability.dependencies import get_llm_call_log_service
from app.domains.observability.entities import LlmCallLog
from app.domains.observability.schemas import (
    LlmCallLogCreate,
    LlmCallLogResponse,
    LlmCallLogUpdate,
)


def llm_call_log_filters(
    enrollment_id: Annotated[int | None, Query()] = None,
    task: Annotated[str | None, Query()] = None,
    model: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    return {"enrollment_id": enrollment_id, "task": task, "model": model, "status": status}


routers: list[APIRouter] = [
    build_crud_router(
        prefix="/llm-call-logs",
        read_guard=require_roles(*ADMIN),
        write_guard=require_roles(*ADMIN),
        tag="llm-call-logs",
        get_service=get_llm_call_log_service,
        entity_cls=LlmCallLog,
        create_schema=LlmCallLogCreate,
        update_schema=LlmCallLogUpdate,
        response_schema=LlmCallLogResponse,
        filters=llm_call_log_filters,
    ),
]
