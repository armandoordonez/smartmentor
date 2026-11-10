"""Entidades de solo lectura de observabilidad (Python puro)."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class LlmCallLog:
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
    created_at: datetime | None


@dataclass(frozen=True)
class LogFilters:
    task: str | None = None
    model: str | None = None
    prompt_id: str | None = None
    status: str | None = None


@dataclass(frozen=True)
class TaskSummary:
    task: str
    calls: int
    invalid_json_rate: float
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    cost_usd: float


@dataclass(frozen=True)
class CourseCost:
    course_id: int | None
    calls: int
    cost_usd: float


@dataclass(frozen=True)
class LogSummary:
    by_task: list[TaskSummary]
    by_course: list[CourseCost]
    total_cost_usd: float


@dataclass(frozen=True)
class PathScope:
    learning_path_id: int
    course_id: int


@dataclass(frozen=True)
class ItemValidityRow:
    """Un ítem con sus votos (vista `v_item_validity`)."""

    valid_votes: int
    invalid_votes: int
    slot1_verdict: str | None
    slot2_verdict: str | None


@dataclass(frozen=True)
class LlmStats:
    calls: int = 0
    invalid_outputs: int = 0
    cache_hits: int = 0
    latency_p95_ms: float | None = None
    cost_usd: float = 0.0


@dataclass(frozen=True)
class StepStats:
    steps_passed: int = 0
    passed_first_attempt: int = 0
    avg_attempts_used: float | None = None
    attempts_exhausted: int = 0


@dataclass(frozen=True)
class VideoTopicRanking:
    """Los candidatos de un tema por puesto, con la pertinencia dada por los jueces."""

    topic_id: int
    relevance: list[bool | None] = field(default_factory=list)
