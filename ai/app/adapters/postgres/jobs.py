"""``ai_jobs`` on PostgreSQL (ADR 0010). The public ``job_id`` is ``ai_jobs.public_id``.

``ai_jobs`` has no ``retryable`` nor ``contract`` column: ``retryable`` derives from the error
code (``app/domain/errors.py``) and the contract from the job type.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.errors import RETRYABLE
from app.ports.jobs import Job, JobError, JobPage, JobRefs, JobStatus, NewJob, RequestedBy

_COLUMNS = """
    j.public_id, j.job_type, j.status, j.idempotency_key, j.input, j.result, j.error_code,
    j.error_message, j.attempts, j.requested_by, j.course_id, j.topic_id, j.enrollment_id,
    j.created_at, j.started_at, j.finished_at, j.locked_until
"""


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def input_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def row_to_job(row: RowMapping, *, reclaimed: bool = False) -> Job:
    code = row["error_code"]
    error = (
        JobError(
            code=code, message=row["error_message"] or "", retryable=RETRYABLE.get(code, False)
        )
        if code
        else None
    )
    requested_by = row["requested_by"] if row["requested_by"] in ("api", "eval") else "api"
    return Job(
        id=row["public_id"],
        job_type=row["job_type"],
        status=cast(JobStatus, row["status"]),
        idempotency_key=row["idempotency_key"],
        input=_json(row["input"]),
        refs=JobRefs(
            course_id=row["course_id"],
            topic_id=row["topic_id"],
            enrollment_id=row["enrollment_id"],
        ),
        requested_by=cast(RequestedBy, requested_by),
        attempts=row["attempts"],
        created_at=row["created_at"],
        result=_json(row["result"]),
        error=error,
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        locked_until=row["locked_until"],
        reclaimed=reclaimed,
    )


class PostgresJobRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def create_or_get(self, new: NewJob, now: datetime) -> tuple[Job, bool]:
        params = {
            "job_type": new.job_type,
            "key": new.idempotency_key,
            "sha": input_sha256(new.input),
            "input": json.dumps(new.input, ensure_ascii=False),
            "requested_by": new.requested_by,
            "course_id": new.refs.course_id,
            "topic_id": new.refs.topic_id,
            "enrollment_id": new.refs.enrollment_id,
            "now": now,
        }
        async with self._engine.begin() as conn:
            inserted = (
                (
                    await conn.execute(
                        text(
                            f"""
                        INSERT INTO ai_jobs AS j (job_type, idempotency_key, input_sha256, input,
                            requested_by, course_id, topic_id, enrollment_id, created_at)
                        VALUES (:job_type, :key, :sha, CAST(:input AS jsonb), :requested_by,
                            :course_id, :topic_id, :enrollment_id, :now)
                        ON CONFLICT (idempotency_key) DO NOTHING
                        RETURNING {_COLUMNS}
                        """
                        ),
                        params,
                    )
                )
                .mappings()
                .first()
            )
            if inserted is not None:
                return row_to_job(inserted), True
            existing = (
                (
                    await conn.execute(
                        text(f"SELECT {_COLUMNS} FROM ai_jobs j WHERE j.idempotency_key = :key"),
                        {"key": new.idempotency_key},
                    )
                )
                .mappings()
                .one()
            )
            return row_to_job(existing), False

    async def get(self, job_id: UUID) -> Job | None:
        async with self._engine.connect() as conn:
            row = (
                (
                    await conn.execute(
                        text(
                            f"SELECT {_COLUMNS} FROM ai_jobs j WHERE j.public_id = :id AND j.active"
                        ),
                        {"id": job_id},
                    )
                )
                .mappings()
                .first()
            )
        return row_to_job(row) if row is not None else None

    async def list(
        self,
        *,
        status: JobStatus | None,
        job_type: str | None,
        course_id: int | None,
        limit: int,
        offset: int,
    ) -> JobPage:
        where = ["j.active"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status is not None:
            where.append("j.status = :status")
            params["status"] = status
        if job_type is not None:
            where.append("j.job_type = :job_type")
            params["job_type"] = job_type
        if course_id is not None:
            where.append("j.course_id = :course_id")
            params["course_id"] = course_id
        condition = " AND ".join(where)
        async with self._engine.connect() as conn:
            total = (
                await conn.execute(
                    text(f"SELECT count(*) FROM ai_jobs j WHERE {condition}"),
                    params,
                )
            ).scalar_one()
            rows = (
                (
                    await conn.execute(
                        text(
                            f"SELECT {_COLUMNS} FROM ai_jobs j WHERE {condition} "
                            "ORDER BY j.created_at DESC, j.id DESC LIMIT :limit OFFSET :offset"
                        ),
                        params,
                    )
                )
                .mappings()
                .all()
            )
        return JobPage(items=[row_to_job(r) for r in rows], total=int(total))

    async def claim_next(self, now: datetime, lease_seconds: int) -> Job | None:
        async with self._engine.begin() as conn:
            row = (
                (
                    await conn.execute(
                        text(
                            f"""
                        WITH candidate AS (
                            SELECT id, status AS previous_status
                            FROM ai_jobs
                            WHERE active
                              AND status IN ('queued', 'running')
                              AND (locked_until IS NULL OR locked_until <= :now)
                            ORDER BY created_at, id
                            LIMIT 1
                            FOR UPDATE SKIP LOCKED
                        )
                        UPDATE ai_jobs AS j
                        SET status = 'running',
                            attempts = j.attempts + 1,
                            started_at = coalesce(j.started_at, :now),
                            locked_until = :now + make_interval(secs => :lease)
                        FROM candidate c
                        WHERE j.id = c.id
                        RETURNING {_COLUMNS}, c.previous_status
                        """
                        ),
                        {"now": now, "lease": lease_seconds},
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        return row_to_job(row, reclaimed=row["previous_status"] == "running")

    async def succeed(
        self, job_id: UUID, result: dict[str, Any], contract: str, now: datetime
    ) -> None:
        del contract  # derived from the job type when read
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    UPDATE ai_jobs SET status = 'succeeded', result = CAST(:result AS jsonb),
                        error_code = NULL, error_message = NULL, finished_at = :now,
                        locked_until = NULL
                    WHERE public_id = :id
                    """
                ),
                {"id": job_id, "result": json.dumps(result, ensure_ascii=False), "now": now},
            )

    async def fail(self, job_id: UUID, error: JobError, now: datetime) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    UPDATE ai_jobs SET status = 'failed', error_code = :code,
                        error_message = :message, finished_at = :now, locked_until = NULL
                    WHERE public_id = :id
                    """
                ),
                {"id": job_id, "code": error.code, "message": error.message, "now": now},
            )

    async def requeue(
        self, job_id: UUID, error: JobError, not_before: datetime, now: datetime
    ) -> None:
        del now
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    UPDATE ai_jobs SET status = 'queued', error_code = :code,
                        error_message = :message, locked_until = :not_before
                    WHERE public_id = :id
                    """
                ),
                {
                    "id": job_id,
                    "code": error.code,
                    "message": error.message,
                    "not_before": not_before,
                },
            )

    async def retry(self, job_id: UUID, now: datetime) -> Job | None:
        del now
        retryable = [code for code, flag in RETRYABLE.items() if flag]
        async with self._engine.begin() as conn:
            row = (
                (
                    await conn.execute(
                        text(
                            f"""
                        UPDATE ai_jobs AS j SET status = 'queued', error_code = NULL,
                            error_message = NULL, finished_at = NULL, locked_until = NULL
                        WHERE j.public_id = :id AND j.status = 'failed'
                          AND j.error_code = ANY(:codes)
                        RETURNING {_COLUMNS}
                        """
                        ),
                        {"id": job_id, "codes": retryable},
                    )
                )
                .mappings()
                .first()
            )
        return row_to_job(row) if row is not None else None
