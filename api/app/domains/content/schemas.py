"""Contratos HTTP de contenido (docs/contracts/api-v2.md, secciones 4 y 5)."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.common.schemas import RequestSchema, UtcDatetime

ReviewDecision = Literal["approved", "retired"]
YoutubeId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{11}$")]


class ResourceReview(RequestSchema):
    review_status: ReviewDecision


class ResourceResponse(BaseModel):
    id: int
    topic_id: int
    resource_type: str
    kind: str
    audience: str
    version: int
    version_label: str
    review_status: str
    url: str | None
    content: dict[str, Any] | None
    faithfulness: float | None
    unsupported_claims: list[Any] | None
    sources: list[Any] | None
    prompt_version: str | None
    edited_by_user_id: int | None
    video_candidate_id: int | None
    created_at: UtcDatetime | None
    updated_at: UtcDatetime | None


class ResourceEditResponse(ResourceResponse):
    faithfulness_job_id: str


class RubricCriterionIn(RequestSchema):
    criterion: str = Field(min_length=1, max_length=1000)
    points: float = Field(gt=0, le=1)


class ItemUpdate(RequestSchema):
    review_status: ReviewDecision | None = None
    stem: str | None = Field(default=None, min_length=1, max_length=4000)
    options: list[str] | None = Field(default=None, max_length=4)
    correct_option: int | None = Field(default=None, ge=0, le=3)
    model_answer: str | None = Field(default=None, min_length=1, max_length=4000)
    rubric: list[RubricCriterionIn] | None = Field(default=None, max_length=3)


class ItemResponse(BaseModel):
    id: int
    topic_id: int
    learning_outcome_id: int | None
    source: str
    item_type: str
    bloom_level: str
    difficulty: int
    stem: str
    options: list[Any] | None
    correct_option: int | None
    model_answer: str | None
    rubric: list[Any] | None
    equivalence_group: str | None
    review_status: str
    auto_review: dict[str, Any] | None
    prompt_version: str | None
    created_at: UtcDatetime | None
    updated_at: UtcDatetime | None


class VideoPatch(RequestSchema):
    status: Literal["in_use", "backup", "rejected"] | None = None
    is_relevant: bool | None = None


class VideoCreate(RequestSchema):
    youtube_video_id: YoutubeId
    title: str = Field(min_length=1, max_length=500)
    channel: str | None = Field(default=None, max_length=300)
    duration_seconds: int | None = Field(default=None, ge=1)
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}$")


class VideoResponse(BaseModel):
    id: int
    topic_id: int
    youtube_video_id: str
    url: str
    title: str
    channel: str | None
    duration_seconds: int | None
    language: str | None
    has_captions: bool | None
    characterization: str | None
    characterization_source: str | None
    similarity: float | None
    rank: int | None
    status: str
    origin: str
    relevance_judgment: bool | None


class VideoListResponse(BaseModel):
    topic_id: int
    has_backup: bool
    candidates: list[VideoResponse]


class VideoQualityItem(BaseModel):
    video: VideoResponse
    topic_name: str
    ratings: int
    by_rating: dict[str, int]
    watched_fully: int
    useful_rate: float | None
    quality_index: float | None
    measuring: bool


class VideoQualityResponse(BaseModel):
    learning_path_id: int
    items: list[VideoQualityItem]


class VideoFeedbackCreate(RequestSchema):
    video_candidate_id: int = Field(gt=0)
    enrollment_id: int = Field(gt=0)
    rating: Literal["useful", "audio_issue", "outdated", "too_long"]
    comment: str | None = Field(default=None, max_length=2000)
    watched_fully: bool | None = None


class VideoFeedbackResponse(BaseModel):
    video_candidate_id: int
    enrollment_id: int
    rating: str
    comment: str | None
    watched_fully: bool | None
    created: bool
