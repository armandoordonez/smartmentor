"""Job worker loop (ADR 0010): claim with ``SELECT ... FOR UPDATE SKIP LOCKED``, run, store.

* The claim sets ``status=running``, ``attempts + 1`` and a lease (``locked_until``). A job whose
  lease expired (crashed worker) is claimed again; past ``AI_JOB_MAX_ATTEMPTS`` it fails.
* Transient errors (``AUTO_RETRY``) go back to ``queued`` with a growing backoff, using
  ``locked_until`` as "not before", until ``AI_JOB_MAX_ATTEMPTS``.
* Any other ``TaskError`` ends the job ``failed`` with its code and ``retryable`` flag; an
  unexpected exception ends it with ``INTERNAL_ERROR``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import ValidationError

from app.application.jobs import JobContext, JobService, UnknownJobTypeError
from app.core.logging import job_id_var
from app.domain.errors import AUTO_RETRY, RETRYABLE, TaskError
from app.ports.jobs import Job, JobError, JobRepository

logger = logging.getLogger("app.worker")


@dataclass(frozen=True)
class WorkerConfig:
    lease_seconds: int = 900
    max_attempts: int = 3
    backoff_seconds: int = 30
    poll_seconds: float = 2.0


class JobWorker:
    def __init__(
        self,
        *,
        jobs: JobRepository,
        service: JobService,
        config: WorkerConfig,
        clock: Callable[[], datetime],
    ) -> None:
        self._jobs = jobs
        self._service = service
        self._config = config
        self._clock = clock
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run_once(self) -> Job | None:
        """Claim and process one job. Returns the claimed job (``None`` when idle)."""
        job = await self._jobs.claim_next(self._clock(), self._config.lease_seconds)
        if job is None:
            return None
        token = job_id_var.set(str(job.id))
        try:
            await self._process(job)
        finally:
            job_id_var.reset(token)
        return job

    async def _process(self, job: Job) -> None:
        extra = {"job_type": job.job_type, "attempts": job.attempts}
        if job.reclaimed and job.attempts > self._config.max_attempts:
            # Its worker died again and again (for example, out of memory): stop retrying.
            await self._fail(job, TaskError("INTERNAL_ERROR", "worker lost the job too often"))
            return
        logger.info("job started", extra=extra)
        try:
            handler = self._service.handler(job.job_type)
            payload = handler.parse(job.input)
            ctx = JobContext(
                job_id=job.id, job_type=job.job_type, refs=job.refs, attempt=job.attempts
            )
            result = await handler.run(payload, ctx)
        except TaskError as exc:
            await self._handle_task_error(job, exc)
            return
        except (UnknownJobTypeError, ValidationError) as exc:
            # Stored input that no longer parses: a code change, not a transient failure.
            await self._fail(
                job, TaskError("INTERNAL_ERROR", f"cannot run job: {exc.__class__.__name__}")
            )
            return
        except Exception as exc:
            logger.error("job crashed: %s", exc.__class__.__name__, exc_info=exc, extra=extra)
            await self._handle_task_error(
                job, TaskError("INTERNAL_ERROR", f"unexpected error: {exc.__class__.__name__}")
            )
            return
        await self._jobs.succeed(
            job.id, result.model_dump(mode="json"), handler.contract, self._clock()
        )
        logger.info("job succeeded", extra=extra)

    async def _handle_task_error(self, job: Job, exc: TaskError) -> None:
        if exc.code in AUTO_RETRY and job.attempts < self._config.max_attempts:
            now = self._clock()
            delay = self._config.backoff_seconds * job.attempts
            await self._jobs.requeue(
                job.id,
                JobError(code=exc.code, message=exc.message, retryable=True),
                now + timedelta(seconds=delay),
                now,
            )
            logger.warning("job requeued", extra={"code": exc.code, "attempts": job.attempts})
            return
        await self._fail(job, exc)

    async def _fail(self, job: Job, exc: TaskError) -> None:
        # ai_jobs has no retryable column: the flag always derives from the code.
        retryable = RETRYABLE.get(exc.code, False)
        await self._jobs.fail(
            job.id, JobError(code=exc.code, message=exc.message, retryable=retryable), self._clock()
        )
        logger.warning("job failed", extra={"code": exc.code, "attempts": job.attempts})

    async def run_forever(self) -> None:
        logger.info("worker started")
        while not self._stop.is_set():
            try:
                job = await self.run_once()
            except Exception as exc:  # database down, etc.: wait and try again
                logger.error("worker loop error: %s", exc.__class__.__name__, exc_info=exc)
                job = None
            if job is None:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._stop.wait(), timeout=self._config.poll_seconds)
        logger.info("worker stopped")
