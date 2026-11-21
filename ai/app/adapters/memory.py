"""In-memory adapters of the persistence ports (tests and runs without a database).

They follow the same rules as the PostgreSQL adapters (idempotency, claim, lease, retry) so the
application code is exercised the same way. Not shared between processes: the HTTP service and
the worker need PostgreSQL to talk to each other.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.ports.cache import CachedGeneration
from app.ports.call_logs import LlmCallLog, PromptUsage
from app.ports.catalog import SyllabusDocumentRecord, TopicRecord
from app.ports.jobs import Job, JobError, JobPage, JobStatus, NewJob


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[UUID, Job] = {}
        self._by_key: dict[str, UUID] = {}
        self._lock = asyncio.Lock()

    async def create_or_get(self, new: NewJob, now: datetime) -> tuple[Job, bool]:
        async with self._lock:
            existing = self._by_key.get(new.idempotency_key)
            if existing is not None:
                return self._jobs[existing], False
            job = Job(
                id=uuid.uuid4(),
                job_type=new.job_type,
                status="queued",
                idempotency_key=new.idempotency_key,
                input=new.input,
                refs=new.refs,
                requested_by=new.requested_by,
                attempts=0,
                created_at=now,
            )
            self._jobs[job.id] = job
            self._by_key[new.idempotency_key] = job.id
            return job, True

    async def get(self, job_id: UUID) -> Job | None:
        return self._jobs.get(job_id)

    async def list(
        self,
        *,
        status: JobStatus | None,
        job_type: str | None,
        course_id: int | None,
        limit: int,
        offset: int,
    ) -> JobPage:
        jobs = [
            j
            for j in sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
            if (status is None or j.status == status)
            and (job_type is None or j.job_type == job_type)
            and (course_id is None or j.refs.course_id == course_id)
        ]
        return JobPage(items=jobs[offset : offset + limit], total=len(jobs))

    def _runnable(self, job: Job, now: datetime) -> bool:
        lease_over = job.locked_until is None or job.locked_until <= now
        return job.status in ("queued", "running") and lease_over

    async def claim_next(self, now: datetime, lease_seconds: int) -> Job | None:
        async with self._lock:
            candidates = sorted(
                (j for j in self._jobs.values() if self._runnable(j, now)),
                key=lambda j: j.created_at,
            )
            if not candidates:
                return None
            job = replace(
                candidates[0],
                reclaimed=candidates[0].status == "running",
                status="running",
                attempts=candidates[0].attempts + 1,
                started_at=candidates[0].started_at or now,
                locked_until=now + timedelta(seconds=lease_seconds),
            )
            self._jobs[job.id] = job
            return job

    async def succeed(
        self, job_id: UUID, result: dict[str, Any], contract: str, now: datetime
    ) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = replace(
                job,
                status="succeeded",
                result=result,
                contract=contract,
                error=None,
                finished_at=now,
                locked_until=None,
            )

    async def fail(self, job_id: UUID, error: JobError, now: datetime) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = replace(
                job, status="failed", error=error, finished_at=now, locked_until=None
            )

    async def requeue(
        self, job_id: UUID, error: JobError, not_before: datetime, now: datetime
    ) -> None:
        del now
        async with self._lock:
            job = self._jobs[job_id]
            self._jobs[job_id] = replace(job, status="queued", error=error, locked_until=not_before)

    async def retry(self, job_id: UUID, now: datetime) -> Job | None:
        del now
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status != "failed" or job.error is None:
                return None
            if not job.error.retryable:
                return None
            updated = replace(job, status="queued", error=None, finished_at=None, locked_until=None)
            self._jobs[job_id] = updated
            return updated


class InMemoryCallLogRepository:
    def __init__(self) -> None:
        self.rows: list[LlmCallLog] = []

    async def add(self, log: LlmCallLog) -> None:
        self.rows.append(log)

    async def for_job(self, job_id: UUID) -> list[LlmCallLog]:
        return [r for r in self.rows if r.ai_job_id == job_id]

    async def spent_usd(
        self,
        *,
        since: datetime | None = None,
        course_id: int | None = None,
        enrollment_id: int | None = None,
    ) -> Decimal:
        total = Decimal(0)
        for row in self.rows:
            if since is not None and row.created_at < since:
                continue
            if course_id is not None and row.course_id != course_id:
                continue
            if enrollment_id is not None and row.enrollment_id != enrollment_id:
                continue
            total += row.cost_usd or Decimal(0)
        return total

    async def prompt_usage(self) -> list[PromptUsage]:
        counts: dict[tuple[str, str], list[int]] = {}
        for row in self.rows:
            if row.prompt_id is None or row.prompt_version is None or row.from_cache:
                continue
            entry = counts.setdefault((row.prompt_id, row.prompt_version), [0, 0])
            entry[0] += 1
            entry[1] += row.status == "invalid_output"
        return [
            PromptUsage(prompt_id=p, prompt_version=v, calls=c, invalid_output=i)
            for (p, v), (c, i) in sorted(counts.items())
        ]


class InMemoryGenerationCache:
    def __init__(self) -> None:
        self.entries: dict[str, CachedGeneration] = {}

    async def get(self, key: str) -> CachedGeneration | None:
        return self.entries.get(key)

    async def put(self, entry: CachedGeneration) -> None:
        self.entries.setdefault(entry.cache_key, entry)


class InMemoryCatalogReader:
    def __init__(
        self,
        *,
        documents: Sequence[SyllabusDocumentRecord] = (),
        topics: Sequence[TopicRecord] = (),
    ) -> None:
        self.documents = {d.id: d for d in documents}
        self.topic_list = list(topics)

    async def syllabus_document(self, document_id: int) -> SyllabusDocumentRecord | None:
        return self.documents.get(document_id)

    async def course_topics(self, course_id: int) -> list[TopicRecord]:
        found = [t for t in self.topic_list if t.course_id == course_id]
        return sorted(found, key=lambda t: t.position)

    async def topics(self, topic_ids: Sequence[str]) -> list[TopicRecord]:
        wanted = set(topic_ids)
        return [t for t in self.topic_list if t.id in wanted]
