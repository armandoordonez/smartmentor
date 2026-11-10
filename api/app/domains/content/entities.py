"""Entidades del dominio de contenido (Python puro)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.common.entities import BaseEntity


@dataclass(kw_only=True)
class Resource(BaseEntity):
    topic_id: int
    resource_type: str = "text"
    kind: str = "main"
    audience: str = "all_learners"
    enrollment_id: int | None = None
    version: int = 1
    review_status: str = "pending_review"
    url: str | None = None
    content: str | None = None
    faithfulness: float | None = None
    unsupported_claims: list[Any] | None = None
    sources: list[Any] | None = None
    prompt_version: str | None = None
    edited_by_user_id: int | None = None
    video_candidate_id: int | None = None
    updated_at: datetime | None = None


@dataclass(kw_only=True)
class AssessmentItem(BaseEntity):
    topic_id: int
    learning_outcome_id: int | None = None
    source: str
    item_type: str
    bloom_level: str
    difficulty: int
    stem: str
    options: list[Any] | None = None
    correct_option: str | None = None
    model_answer: str | None = None
    rubric: list[Any] | None = None
    equivalence_group: str | None = None
    review_status: str = "pending_review"
    auto_review: dict[str, Any] | None = None
    prompt_version: str | None = None
    ai_job_id: int | None = None
    updated_at: datetime | None = None


@dataclass(kw_only=True)
class VideoCandidate(BaseEntity):
    topic_id: int
    youtube_video_id: str
    title: str
    channel: str | None = None
    duration_seconds: int | None = None
    language: str | None = None
    has_captions: bool | None = None
    characterization: str | None = None
    characterization_source: str | None = None
    similarity: float | None = None
    rank: int | None = None
    status: str = "candidate"
    origin: str = "youtube_api"
    updated_at: datetime | None = None


@dataclass(kw_only=True)
class VideoRelevanceJudgment(BaseEntity):
    video_candidate_id: int
    judge_user_id: int
    is_relevant: bool


@dataclass(kw_only=True)
class VideoFeedback(BaseEntity):
    video_candidate_id: int
    enrollment_id: int
    rating: str
    comment: str | None = None
    watched_fully: bool | None = None


@dataclass(frozen=True)
class RatingSummary:
    """Calificaciones de un video para la calidad (D5f)."""

    video_candidate_id: int
    ratings: dict[str, int] = field(default_factory=dict)
    watched_fully: int = 0
