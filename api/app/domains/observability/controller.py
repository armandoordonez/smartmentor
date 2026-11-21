"""Endpoints de observabilidad (solo lectura): registro del LLM y métricas de evaluación."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.auth.dependencies import require_roles
from app.auth.policies import ADMIN, STAFF
from app.common.schemas import Page, UtcDatetime
from app.domains.identity.authentication import CurrentUser
from app.domains.observability.catalog import metric_catalog
from app.domains.observability.dependencies import get_log_service, get_metrics_service
from app.domains.observability.entities import LlmCallLog, LogFilters
from app.domains.observability.service import LogService, MetricsService

AdminUser = Annotated[CurrentUser, Depends(require_roles(*ADMIN))]
StaffUser = Annotated[CurrentUser, Depends(require_roles(*STAFF))]
LogServiceDep = Annotated[LogService, Depends(get_log_service)]
MetricsServiceDep = Annotated[MetricsService, Depends(get_metrics_service)]


class LlmCallLogResponse(BaseModel):
    """Una llamada al LLM. Guarda el `input_sha256`, nunca el texto enviado (ADR 0018)."""

    id: int
    ai_job_id: int | None
    enrollment_id: int | None
    provider: str | None
    task: str
    model: str | None
    prompt_id: str | None
    prompt_version: str | None
    input_sha256: str | None
    json_valid: bool | None
    call_attempt: int
    from_cache: bool
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    latency_ms: int | None
    status: str
    error_message: str | None
    created_at: UtcDatetime | None


class TaskSummaryResponse(BaseModel):
    task: str
    calls: int
    invalid_json_rate: float
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    cost_usd: float


class CourseCostResponse(BaseModel):
    course_id: int | None
    calls: int
    cost_usd: float


class LogSummaryResponse(BaseModel):
    by_task: list[TaskSummaryResponse]
    by_course: list[CourseCostResponse]
    total_cost_usd: float


def _filters(
    task: Annotated[str | None, Query(description="Tarea (`items.generate_quiz_bank`...)")] = None,
    model: Annotated[str | None, Query()] = None,
    prompt_id: Annotated[str | None, Query()] = None,
    status: Annotated[
        str | None, Query(pattern="^(success|error|invalid_output|budget_exceeded)$")
    ] = None,
) -> LogFilters:
    return LogFilters(task=task, model=model, prompt_id=prompt_id, status=status)


FiltersDep = Annotated[LogFilters, Depends(_filters)]


def _log(entry: LlmCallLog) -> LlmCallLogResponse:
    return LlmCallLogResponse(**asdict(entry))


router = APIRouter(tags=["observability"])


@router.get("/llm-call-logs", response_model=Page[LlmCallLogResponse])
async def list_llm_call_logs(
    _admin: AdminUser,
    service: LogServiceDep,
    filters: FiltersDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[LlmCallLogResponse]:
    """Llamadas al LLM, de la más reciente a la más antigua (AD2); filtra por tarea y modelo."""
    entries, total = await service.search(filters, limit=limit, offset=offset)
    return Page[LlmCallLogResponse](
        items=[_log(e) for e in entries], total=total, limit=limit, offset=offset
    )


@router.get("/llm-call-logs/summary", response_model=LogSummaryResponse)
async def llm_call_logs_summary(
    _admin: AdminUser, service: LogServiceDep, filters: FiltersDep
) -> LogSummaryResponse:
    """Por tarea: llamadas, JSON inválido, latencia p50 y p95 y costo; más el costo por curso."""
    summary = await service.summary(filters)
    return LogSummaryResponse(
        by_task=[TaskSummaryResponse(**asdict(t)) for t in summary.by_task],
        by_course=[CourseCostResponse(**asdict(c)) for c in summary.by_course],
        total_cost_usd=summary.total_cost_usd,
    )


@router.get("/metrics/evaluation", response_model=dict[str, Any])
async def evaluation_metrics(
    user: StaffUser,
    service: MetricsServiceDep,
    learning_path_id: Annotated[int | None, Query(gt=0)] = None,
) -> dict[str, Any]:
    """Métricas del brief calculables en SQL. El administrador ve todo; el instructor, sus rutas.

    `groups` (aditivo, 2026-11-12) es el catálogo de AD3: cada métrica con su meta y su estado.
    """
    found = await service.evaluation(user, learning_path_id)
    return {**asdict(found), "groups": metric_catalog(found)}


routers: list[APIRouter] = [router]
