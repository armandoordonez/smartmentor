"""Job types and the job service (``POST/GET /v1/jobs``, ADR 0010).

A ``JobHandler`` declares its ``job_type``, the Pydantic model of its ``input`` and the contract
of its ``result``. New job types (Phase 5) only add a handler to the registry built in
``app/container.py``; nothing else changes.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.application.llm_runner import CallContext
from app.ports.budget import BudgetScope
from app.ports.call_logs import LlmCallLogRepository
from app.ports.jobs import Job, JobPage, JobRefs, JobRepository, JobStatus, NewJob, RequestedBy


@dataclass(frozen=True)
class JobContext:
    job_id: UUID
    job_type: str
    refs: JobRefs
    attempt: int

    def call(self) -> CallContext:
        return CallContext(
            task=self.job_type,
            job_id=self.job_id,
            scope=BudgetScope(course_id=self.refs.course_id, enrollment_id=self.refs.enrollment_id),
        )


class JobHandler[I: BaseModel](ABC):
    job_type: str
    contract: str  # e.g. "syllabus.v1"
    input_model: type[I]

    def parse(self, raw: Mapping[str, Any]) -> I:
        return self.input_model.model_validate(raw)

    @abstractmethod
    async def run(self, payload: I, ctx: JobContext) -> BaseModel: ...


class UnknownJobTypeError(Exception):
    pass


class InvalidJobInputError(Exception):
    def __init__(self, error: ValidationError) -> None:
        super().__init__(str(error))
        self.error = error


class IdempotencyKeyReusedError(Exception):
    pass


class JobNotFoundError(Exception):
    pass


class JobNotRetryableError(Exception):
    pass


@dataclass(frozen=True)
class JobView:
    job: Job
    cost_usd: Decimal | None


def canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class JobService:
    def __init__(
        self,
        *,
        jobs: JobRepository,
        call_logs: LlmCallLogRepository,
        handlers: Mapping[str, JobHandler[Any]],
        clock: Callable[[], datetime],
    ) -> None:
        self._jobs = jobs
        self._logs = call_logs
        self._handlers = handlers
        self._clock = clock

    @property
    def job_types(self) -> list[str]:
        return sorted(self._handlers)

    def handler(self, job_type: str) -> JobHandler[Any]:
        handler = self._handlers.get(job_type)
        if handler is None:
            raise UnknownJobTypeError(job_type)
        return handler

    async def create(
        self,
        *,
        job_type: str,
        idempotency_key: str,
        raw_input: Mapping[str, Any],
        refs: JobRefs,
        requested_by: RequestedBy,
    ) -> tuple[Job, bool]:
        handler = self.handler(job_type)
        try:
            payload = handler.parse(raw_input)
        except ValidationError as exc:
            raise InvalidJobInputError(exc) from exc
        normalized = payload.model_dump(mode="json")
        job, created = await self._jobs.create_or_get(
            NewJob(
                job_type=job_type,
                idempotency_key=idempotency_key,
                input=normalized,
                refs=refs,
                requested_by=requested_by,
            ),
            self._clock(),
        )
        if not created and (
            job.job_type != job_type or canonical(job.input) != canonical(normalized)
        ):
            raise IdempotencyKeyReusedError(idempotency_key)
        return job, created

    async def cost(self, job_id: UUID) -> Decimal | None:
        logs = await self._logs.for_job(job_id)
        if any(log.cost_usd is None for log in logs):
            return None
        return sum((log.cost_usd or Decimal(0) for log in logs), Decimal(0))

    async def get(self, job_id: UUID) -> JobView:
        job = await self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(str(job_id))
        return JobView(job=job, cost_usd=await self.cost(job_id))

    async def list(
        self,
        *,
        status: JobStatus | None,
        job_type: str | None,
        course_id: int | None,
        limit: int,
        offset: int,
    ) -> JobPage:
        return await self._jobs.list(
            status=status, job_type=job_type, course_id=course_id, limit=limit, offset=offset
        )

    async def retry(self, job_id: UUID) -> Job:
        job = await self._jobs.retry(job_id, self._clock())
        if job is not None:
            return job
        if await self._jobs.get(job_id) is None:
            raise JobNotFoundError(str(job_id))
        raise JobNotRetryableError(str(job_id))
