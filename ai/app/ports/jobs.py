"""``JobRepository`` port: the ``ai_jobs`` queue (ADR 0010).

States: ``queued`` -> ``running`` -> ``succeeded`` | ``failed``; ``failed`` -> ``queued`` with
``/retry``. ``locked_until`` is the lease of a running job (a crashed worker's job is claimed
again when it expires) and, for a queued job, the earliest time it may run (retry backoff).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

JobStatus = Literal["queued", "running", "succeeded", "failed"]
RequestedBy = Literal["api", "eval"]


@dataclass(frozen=True)
class JobRefs:
    course_id: int | None = None
    topic_id: int | None = None
    enrollment_id: int | None = None


@dataclass(frozen=True)
class JobError:
    code: str
    message: str
    retryable: bool


@dataclass(frozen=True)
class Job:
    id: UUID
    job_type: str
    status: JobStatus
    idempotency_key: str
    input: dict[str, Any]
    refs: JobRefs
    requested_by: RequestedBy
    attempts: int
    created_at: datetime
    contract: str | None = None
    result: dict[str, Any] | None = None
    error: JobError | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    locked_until: datetime | None = None
    # True when the claim took a running job whose lease expired (its worker died).
    reclaimed: bool = False


@dataclass(frozen=True)
class NewJob:
    job_type: str
    idempotency_key: str
    input: dict[str, Any]
    refs: JobRefs
    requested_by: RequestedBy


@dataclass(frozen=True)
class JobPage:
    items: list[Job]
    total: int


class JobRepository(Protocol):
    async def create_or_get(self, new: NewJob, now: datetime) -> tuple[Job, bool]:
        """Insert a queued job or return the one with the same ``idempotency_key``.

        Returns ``(job, created)``. Comparing the body of an existing key is the caller's job.
        """
        ...

    async def get(self, job_id: UUID) -> Job | None: ...

    async def list(
        self,
        *,
        status: JobStatus | None,
        job_type: str | None,
        course_id: int | None,
        limit: int,
        offset: int,
    ) -> JobPage: ...

    async def claim_next(self, now: datetime, lease_seconds: int) -> Job | None:
        """Take one runnable job (``SELECT ... FOR UPDATE SKIP LOCKED``): status ``running``,
        ``attempts + 1``, ``locked_until = now + lease``. A runnable job is queued with
        ``locked_until`` null or past, or running with an expired lease (crashed worker)."""
        ...

    async def succeed(
        self, job_id: UUID, result: dict[str, Any], contract: str, now: datetime
    ) -> None: ...

    async def fail(self, job_id: UUID, error: JobError, now: datetime) -> None: ...

    async def requeue(
        self, job_id: UUID, error: JobError, not_before: datetime, now: datetime
    ) -> None:
        """Back to ``queued`` after a transient failure, runnable from ``not_before``."""
        ...

    async def retry(self, job_id: UUID, now: datetime) -> Job | None:
        """``failed`` + retryable -> ``queued`` (clears the error). ``None`` when not allowed."""
        ...
