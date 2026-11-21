"""``LlmCallLogRepository`` port: one row per call attempt in ``llm_call_logs`` (plan 5.4.4).

Cache hits and budget refusals are logged too (``from_cache``, ``status=budget_exceeded``) so
AD2 can count them. ``cost_usd`` is ``None`` when the model has no price.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

CallStatus = Literal["success", "error", "invalid_output", "budget_exceeded"]


@dataclass(frozen=True)
class LlmCallLog:
    provider: str
    model: str
    task: str
    prompt_id: str | None
    prompt_version: str | None
    input_sha256: str | None
    call_attempt: int
    from_cache: bool
    status: CallStatus
    json_valid: bool | None
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal | None
    latency_ms: int
    created_at: datetime
    ai_job_id: UUID | None = None
    course_id: int | None = None
    enrollment_id: int | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class PromptUsage:
    """Aggregates per prompt version for ``GET /v1/prompts``."""

    prompt_id: str
    prompt_version: str
    calls: int
    invalid_output: int


class LlmCallLogRepository(Protocol):
    async def add(self, log: LlmCallLog) -> None: ...

    async def for_job(self, job_id: UUID) -> list[LlmCallLog]: ...

    async def spent_usd(
        self,
        *,
        since: datetime | None = None,
        course_id: int | None = None,
        enrollment_id: int | None = None,
    ) -> Decimal:
        """Sum of ``cost_usd`` (null counts as 0) matching every given filter."""
        ...

    async def prompt_usage(self) -> list[PromptUsage]: ...
