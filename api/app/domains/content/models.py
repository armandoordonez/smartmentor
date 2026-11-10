"""Modelos SQLAlchemy de contenido. Reflejan las tablas del esquema v2.0.0 (Liquibase)."""

from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import PublicTableModel, UpdatableTableModel


class ResourceModel(PublicTableModel):
    __tablename__ = "resources"

    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"))
    resource_type: Mapped[str] = mapped_column(String(10))
    kind: Mapped[str] = mapped_column(String(20), server_default="main")
    audience: Mapped[str] = mapped_column(String(15), server_default="all_learners")
    enrollment_id: Mapped[int | None] = mapped_column(BigInteger)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    review_status: Mapped[str] = mapped_column(String(20), server_default="pending_review")
    url: Mapped[str | None] = mapped_column(String(1000))
    content: Mapped[str | None] = mapped_column(Text)
    faithfulness: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    unsupported_claims: Mapped[list[Any] | None] = mapped_column(JSONB)
    sources: Mapped[list[Any] | None] = mapped_column(JSONB)
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    edited_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    video_candidate_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("video_candidates.id")
    )


class AssessmentItemModel(PublicTableModel):
    """Banco de ítems. Lo comparten `content` (revisión) y los dominios que arman las pruebas."""

    __tablename__ = "assessment_items"

    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"))
    learning_outcome_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("learning_outcomes.id")
    )
    source: Mapped[str] = mapped_column(String(15))
    item_type: Mapped[str] = mapped_column(String(20))
    bloom_level: Mapped[str] = mapped_column(String(20))
    difficulty: Mapped[int] = mapped_column(SmallInteger)
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[list[Any] | None] = mapped_column(JSONB)
    correct_option: Mapped[str | None] = mapped_column(String(10))
    model_answer: Mapped[str | None] = mapped_column(Text)
    rubric: Mapped[list[Any] | None] = mapped_column(JSONB)
    equivalence_group: Mapped[str | None] = mapped_column(String(100))
    review_status: Mapped[str] = mapped_column(String(20), server_default="pending_review")
    auto_review: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    ai_job_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ai_jobs.id"))


class VideoCandidateModel(PublicTableModel):
    __tablename__ = "video_candidates"

    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"))
    youtube_video_id: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(500))
    channel: Mapped[str | None] = mapped_column(String(300))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str | None] = mapped_column(String(10))
    has_captions: Mapped[bool | None] = mapped_column(Boolean)
    characterization: Mapped[str | None] = mapped_column(Text)
    characterization_source: Mapped[str | None] = mapped_column(String(30))
    similarity: Mapped[Decimal | None] = mapped_column(Numeric(6, 5))
    rank: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(15), server_default="candidate")
    origin: Mapped[str] = mapped_column(String(15), server_default="youtube_api")


class VideoRelevanceJudgmentModel(UpdatableTableModel):
    __tablename__ = "video_relevance_judgments"

    video_candidate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("video_candidates.id"))
    judge_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    is_relevant: Mapped[bool] = mapped_column(Boolean)


class VideoFeedbackModel(UpdatableTableModel):
    __tablename__ = "video_feedback"

    video_candidate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("video_candidates.id"))
    enrollment_id: Mapped[int] = mapped_column(BigInteger)
    rating: Mapped[str] = mapped_column(String(15))
    comment: Mapped[str | None] = mapped_column(Text)
    watched_fully: Mapped[bool | None] = mapped_column(Boolean)
