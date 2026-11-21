"""Synchronous tasks (< 3 s, ADR 0010): ``levels.estimate`` and ``path.sequence``.

``video.rank`` is added by the content module (Phase 5). They create no ``ai_jobs`` rows
(embedding calls are logged in ``llm_call_logs``).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ContainerDep
from app.application.diagnostic import LevelsEstimateInput
from app.application.llm_runner import CallContext
from app.application.path import PathSequenceInput, sequence
from app.application.video.service import RankInput
from app.core.errors import ApiError
from app.domain.contracts.diagnostic import DiagnosticResult
from app.domain.contracts.learning_path import LearningPath
from app.domain.contracts.video import VideoResource
from app.domain.errors import TaskError
from app.domain.sequencing import SequencingError

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])

_TASK_ERROR_STATUS = {
    "BUDGET_EXCEEDED": (503, "BUDGET_EXCEEDED"),
    "INPUT_REFERENCE_NOT_FOUND": (422, "INPUT_REFERENCE_NOT_FOUND"),
}


def task_error_to_http(exc: TaskError) -> ApiError:
    status, code = _TASK_ERROR_STATUS.get(exc.code, (503, "SERVICE_UNAVAILABLE"))
    return ApiError(status, code, exc.message, extra={"retryable": exc.retryable})


@router.post("/levels.estimate", responses={503: {"description": "BUDGET_EXCEEDED"}})
async def levels_estimate(body: LevelsEstimateInput, container: ContainerDep) -> DiagnosticResult:
    try:
        return await container.level_estimator.estimate(body, CallContext(task="levels.estimate"))
    except TaskError as exc:
        raise task_error_to_http(exc) from exc


@router.post("/path.sequence")
async def path_sequence(body: PathSequenceInput) -> LearningPath:
    try:
        return sequence(body)
    except SequencingError as exc:
        extra = {"cycle": exc.cycle} if exc.cycle else None
        raise ApiError(422, exc.code, str(exc), extra=extra) from exc


@router.post("/video.rank", responses={503: {"description": "BUDGET_EXCEEDED"}})
async def video_rank(body: RankInput, container: ContainerDep) -> VideoResource:
    try:
        return await container.content.recommender.rank(body, CallContext(task="video.rank"))
    except TaskError as exc:
        raise task_error_to_http(exc) from exc


@router.post("/{name}", responses={404: {"description": "UNKNOWN_TASK"}})
async def unknown_task(name: str) -> None:
    raise ApiError(404, "UNKNOWN_TASK", f"Task {name[:60]} does not exist.")
