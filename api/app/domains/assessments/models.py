"""Modelos SQLAlchemy de evaluaciones: diagnostics, assessment_attempts y badges de Liquibase."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TableModel


class DiagnosticModel(TableModel):
    __tablename__ = "diagnostics"

    enrollment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("enrollments.id"))
    questions: Mapped[list[Any]] = mapped_column(JSONB, server_default="[]")
    answers: Mapped[list[Any] | dict[str, Any] | None] = mapped_column(JSONB)
    level_by_topic: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssessmentAttemptModel(TableModel):
    __tablename__ = "assessment_attempts"

    enrollment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("enrollments.id"))
    path_step_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("path_steps.id"))
    assessment_type: Mapped[str] = mapped_column(String(10))
    attempt_number: Mapped[int] = mapped_column(SmallInteger, server_default="1")
    questions: Mapped[list[Any]] = mapped_column(JSONB, server_default="[]")
    answers: Mapped[list[Any] | dict[str, Any] | None] = mapped_column(JSONB)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    passed: Mapped[bool | None] = mapped_column(Boolean)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BadgeModel(TableModel):
    __tablename__ = "badges"

    enrollment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("enrollments.id"))
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    image_url: Mapped[str | None] = mapped_column(String(1000))
    open_badges_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
