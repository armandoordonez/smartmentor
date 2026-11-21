"""``llm_call_logs`` on PostgreSQL (append-only: ``smartmentor_ai`` has SELECT and INSERT only).

The table has no ``course_id``: the course comes from the job (``ai_jobs.course_id``).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine

from app.ports.call_logs import CallStatus, LlmCallLog, PromptUsage

_SELECT = """
    SELECT l.provider, l.model, l.task, l.prompt_id, l.prompt_version, l.input_sha256,
           l.call_attempt, l.from_cache, l.status, l.json_valid, l.input_tokens,
           l.output_tokens, l.cost_usd, l.latency_ms, l.created_at, l.error_message,
           l.enrollment_id, j.public_id AS job_public_id, j.course_id
    FROM llm_call_logs l
    LEFT JOIN ai_jobs j ON j.id = l.ai_job_id
"""


def _row(row: RowMapping) -> LlmCallLog:
    return LlmCallLog(
        provider=row["provider"] or "",
        model=row["model"] or "",
        task=row["task"],
        prompt_id=row["prompt_id"],
        prompt_version=row["prompt_version"],
        input_sha256=row["input_sha256"],
        call_attempt=row["call_attempt"],
        from_cache=row["from_cache"],
        status=cast(CallStatus, row["status"]),
        json_valid=row["json_valid"],
        input_tokens=row["input_tokens"] or 0,
        output_tokens=row["output_tokens"] or 0,
        cost_usd=row["cost_usd"],
        latency_ms=row["latency_ms"] or 0,
        created_at=row["created_at"],
        ai_job_id=row["job_public_id"],
        course_id=row["course_id"],
        enrollment_id=row["enrollment_id"],
        error_message=row["error_message"],
    )


class PostgresCallLogRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def add(self, log: LlmCallLog) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO llm_call_logs (ai_job_id, enrollment_id, provider, task, model,
                        prompt_id, prompt_version, input_sha256, json_valid, call_attempt,
                        from_cache, input_tokens, output_tokens, cost_usd, latency_ms, status,
                        error_message, created_at)
                    VALUES ((SELECT id FROM ai_jobs WHERE public_id = :job_id), :enrollment_id,
                        :provider, :task, :model, :prompt_id, :prompt_version, :input_sha256,
                        :json_valid, :call_attempt, :from_cache, :input_tokens, :output_tokens,
                        :cost_usd, :latency_ms, :status, :error_message, :created_at)
                    """
                ),
                {
                    "job_id": log.ai_job_id,
                    "enrollment_id": log.enrollment_id,
                    "provider": log.provider,
                    "task": log.task,
                    "model": log.model,
                    "prompt_id": log.prompt_id,
                    "prompt_version": log.prompt_version,
                    "input_sha256": log.input_sha256,
                    "json_valid": log.json_valid,
                    "call_attempt": log.call_attempt,
                    "from_cache": log.from_cache,
                    "input_tokens": log.input_tokens,
                    "output_tokens": log.output_tokens,
                    "cost_usd": log.cost_usd,
                    "latency_ms": log.latency_ms,
                    "status": log.status,
                    "error_message": log.error_message,
                    "created_at": log.created_at,
                },
            )

    async def for_job(self, job_id: UUID) -> list[LlmCallLog]:
        async with self._engine.connect() as conn:
            rows = (
                (
                    await conn.execute(
                        text(_SELECT + " WHERE j.public_id = :id ORDER BY l.id"), {"id": job_id}
                    )
                )
                .mappings()
                .all()
            )
        return [_row(r) for r in rows]

    async def spent_usd(
        self,
        *,
        since: datetime | None = None,
        course_id: int | None = None,
        enrollment_id: int | None = None,
    ) -> Decimal:
        where = ["l.active"]
        params: dict[str, Any] = {}
        if since is not None:
            where.append("l.created_at >= :since")
            params["since"] = since
        if course_id is not None:
            where.append("j.course_id = :course_id")
            params["course_id"] = course_id
        if enrollment_id is not None:
            where.append("coalesce(l.enrollment_id, j.enrollment_id) = :enrollment_id")
            params["enrollment_id"] = enrollment_id
        sql = (
            "SELECT coalesce(sum(l.cost_usd), 0) FROM llm_call_logs l "
            "LEFT JOIN ai_jobs j ON j.id = l.ai_job_id WHERE " + " AND ".join(where)
        )
        async with self._engine.connect() as conn:
            total = (await conn.execute(text(sql), params)).scalar_one()
        return Decimal(total)

    async def prompt_usage(self) -> list[PromptUsage]:
        async with self._engine.connect() as conn:
            rows = (
                (
                    await conn.execute(
                        text(
                            """
                        SELECT prompt_id, prompt_version, count(*) AS calls,
                               count(*) FILTER (WHERE status = 'invalid_output') AS invalid
                        FROM llm_call_logs
                        WHERE active AND prompt_id IS NOT NULL AND prompt_version IS NOT NULL
                          AND NOT from_cache
                        GROUP BY prompt_id, prompt_version
                        ORDER BY prompt_id, prompt_version
                        """
                        )
                    )
                )
                .mappings()
                .all()
            )
        return [
            PromptUsage(
                prompt_id=r["prompt_id"],
                prompt_version=r["prompt_version"],
                calls=int(r["calls"]),
                invalid_output=int(r["invalid"]),
            )
            for r in rows
        ]
