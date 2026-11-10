"""Modelos SQLAlchemy de evaluaciones. Reflejan las tablas del esquema v2.0.0 (Liquibase).

`assessment_items` también la edita el instructor desde el dominio de contenido (D5): el modelo
declara `extend_existing` para convivir con otra declaración de la misma tabla.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import PublicTableModel


class AssessmentItemModel(PublicTableModel):
    __tablename__ = "assessment_items"
    __table_args__ = ({"extend_existing": True},)

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


class DiagnosticModel(PublicTableModel):
    __tablename__ = "diagnostics"

    enrollment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("enrollments.id"))
    status: Mapped[str] = mapped_column(String(20), server_default="created")
    item_ids: Mapped[list[Any]] = mapped_column(JSONB, server_default=sql_text("'[]'::jsonb"))
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sql_text("'{}'::jsonb"))
    level_by_topic: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssessmentAttemptModel(PublicTableModel):
    __tablename__ = "assessment_attempts"

    enrollment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("enrollments.id"))
    path_step_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("path_steps.id"))
    assessment_type: Mapped[str] = mapped_column(String(10))
    attempt_number: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(20), server_default="created")
    item_ids: Mapped[list[Any]] = mapped_column(JSONB, server_default=sql_text("'[]'::jsonb"))
    uses_extra_grant: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    passed: Mapped[bool | None] = mapped_column(Boolean)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AttemptAnswerModel(PublicTableModel):
    __tablename__ = "attempt_answers"

    assessment_attempt_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assessment_attempts.id")
    )
    assessment_item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("assessment_items.id"))
    selected_option: Mapped[str | None] = mapped_column(String(10))
    dont_know: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    text_answer: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    grader: Mapped[str | None] = mapped_column(String(10))
    rubric_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    feedback: Mapped[str | None] = mapped_column(Text)
    review_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BadgeModel(PublicTableModel):
    __tablename__ = "badges"

    enrollment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("enrollments.id"))
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sql_text("now()")
    )
    image_url: Mapped[str | None] = mapped_column(String(1000))
    image_path: Mapped[str | None] = mapped_column(String(500))
    open_badges_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
