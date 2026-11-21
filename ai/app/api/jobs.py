"""``/v1/jobs``: create (idempotent), read, list and retry asynchronous jobs (ADR 0010)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.api.deps import ContainerDep
from app.api.schemas import (
    CreateJobRequest,
    JobCreatedResponse,
    JobErrorBody,
    JobListResponse,
    JobRefsBody,
    JobResponse,
    JobSummary,
)
from app.application.jobs import (
    IdempotencyKeyReusedError,
    InvalidJobInputError,
    JobNotFoundError,
    JobNotRetryableError,
    JobService,
    UnknownJobTypeError,
)
from app.core.errors import ApiError, validation_errors
from app.ports.jobs import Job, JobRefs, JobStatus

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


def _contract(service: JobService, job: Job) -> str | None:
    try:
        return service.handler(job.job_type).contract
    except UnknownJobTypeError:
        return job.contract


def summary(service: JobService, job: Job) -> JobSummary:
    error = job.error if job.status == "failed" else None
    return JobSummary(
        job_id=job.id,
        job_type=job.job_type,
        status=job.status,
        contract=_contract(service, job),
        error=JobErrorBody(code=error.code, message=error.message, retryable=error.retryable)
        if error
        else None,
        attempts=job.attempts,
        refs=JobRefsBody(
            course_id=job.refs.course_id,
            topic_id=job.refs.topic_id,
            enrollment_id=job.refs.enrollment_id,
        ),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _not_found(job_id: UUID) -> ApiError:
    return ApiError(404, "JOB_NOT_FOUND", f"Job {job_id} does not exist.")


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    responses={200: {"description": "Same idempotency_key and body: the existing job"}},
)
async def create_job(
    body: CreateJobRequest, container: ContainerDep, response: Response
) -> JobCreatedResponse:
    service = container.job_service
    try:
        job, created = await service.create(
            job_type=body.job_type,
            idempotency_key=body.idempotency_key,
            raw_input=body.input,
            refs=JobRefs(
                course_id=body.refs.course_id,
                topic_id=body.refs.topic_id,
                enrollment_id=body.refs.enrollment_id,
            ),
            requested_by=body.requested_by,
        )
    except UnknownJobTypeError as exc:
        raise ApiError(
            422,
            "UNKNOWN_JOB_TYPE",
            f"Unknown job_type. Known: {', '.join(service.job_types)}.",
        ) from exc
    except InvalidJobInputError as exc:
        raise ApiError(
            422,
            "INVALID_JOB_INPUT",
            "The input does not match the job_type schema.",
            extra={"errors": validation_errors(exc.error.errors(include_url=False))},
        ) from exc
    except IdempotencyKeyReusedError as exc:
        raise ApiError(
            422,
            "IDEMPOTENCY_KEY_REUSED",
            "The idempotency_key was used with another job_type or input.",
        ) from exc
    if not created:
        response.status_code = status.HTTP_200_OK
    return JobCreatedResponse(
        job_id=job.id, job_type=job.job_type, status=job.status, created_at=job.created_at
    )


@router.get("")
async def list_jobs(
    container: ContainerDep,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
    job_type: Annotated[str | None, Query(max_length=60)] = None,
    course_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobListResponse:
    service = container.job_service
    page = await service.list(
        status=status_filter, job_type=job_type, course_id=course_id, limit=limit, offset=offset
    )
    return JobListResponse(
        items=[summary(service, j) for j in page.items],
        total=page.total,
        limit=limit,
        offset=offset,
    )


@router.get("/{job_id}")
async def get_job(job_id: UUID, container: ContainerDep) -> JobResponse:
    service = container.job_service
    try:
        view = await service.get(job_id)
    except JobNotFoundError as exc:
        raise _not_found(job_id) from exc
    job = view.job
    return JobResponse(
        **summary(service, job).model_dump(),
        result=job.result if job.status == "succeeded" else None,
        cost_usd=float(view.cost_usd) if view.cost_usd is not None else None,
    )


@router.post("/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_job(job_id: UUID, container: ContainerDep) -> JobCreatedResponse:
    try:
        job = await container.job_service.retry(job_id)
    except JobNotFoundError as exc:
        raise _not_found(job_id) from exc
    except JobNotRetryableError as exc:
        raise ApiError(
            409, "JOB_NOT_RETRYABLE", "Only failed jobs with retryable=true can be retried."
        ) from exc
    return JobCreatedResponse(
        job_id=job.id, job_type=job.job_type, status=job.status, created_at=job.created_at
    )
