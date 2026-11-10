"""Modelos SQLAlchemy del dominio de rutas. Reflejan las tablas del esquema v2.0.0 (Liquibase)."""

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


class LearningPathModel(PublicTableModel):
    __tablename__ = "learning_paths"

    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("courses.id"))
    name: Mapped[str] = mapped_column(String(200))
    group_label: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    default_objective_bloom_verb: Mapped[str | None] = mapped_column(Text)
    default_objective_content: Mapped[str | None] = mapped_column(Text)
    default_objective_criterion: Mapped[str | None] = mapped_column(Text)
    topic_pass_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default="70")
    final_pass_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default="80")
    mastery_skip_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default="80")
    max_attempts: Mapped[int] = mapped_column(SmallInteger, server_default="3")
    level_weights: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=sql_text('\'{"test": 0.8, "profile": 0.1, "resume": 0.1}\'::jsonb')
    )
    short_answer_min_ratio: Mapped[Decimal] = mapped_column(Numeric(4, 3), server_default="0.667")


class EnrollmentModel(PublicTableModel):
    __tablename__ = "enrollments"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    learning_path_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_paths.id"))
    status: Mapped[str] = mapped_column(String(20), server_default="enrolled")
    profile_description: Mapped[str | None] = mapped_column(Text)
    profile_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    objective_bloom_verb: Mapped[str | None] = mapped_column(String(60))
    objective_content: Mapped[str | None] = mapped_column(Text)
    objective_criterion: Mapped[str | None] = mapped_column(Text)
    objective_origin: Mapped[str | None] = mapped_column(String(20))
    pilot_arm: Mapped[str | None] = mapped_column(String(15))
    analysis_included: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PathStepModel(PublicTableModel):
    __tablename__ = "path_steps"

    enrollment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("enrollments.id"))
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"))
    step_order: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    inclusion_reason: Mapped[str | None] = mapped_column(String(25))
    diagnostic_level: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    attempts_used: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    extra_attempts_granted: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    best_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    last_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))


class AttemptGrantModel(PublicTableModel):
    __tablename__ = "attempt_grants"

    path_step_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("path_steps.id"))
    enrollment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("enrollments.id"))
    granted_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    attempts: Mapped[int] = mapped_column(SmallInteger)
    note: Mapped[str | None] = mapped_column(Text)


class AlertModel(PublicTableModel):
    __tablename__ = "alerts"

    recipient_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    alert_type: Mapped[str] = mapped_column(String(30))
    enrollment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("enrollments.id"))
    path_step_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("path_steps.id"))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
