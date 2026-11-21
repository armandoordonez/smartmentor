"""Modelos SQLAlchemy de evaluación humana. Reflejan las tablas del esquema v2.0.0 (Liquibase)."""

from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import UpdatableTableModel


class CourseEvaluatorModel(UpdatableTableModel):
    __tablename__ = "course_evaluators"

    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("courses.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    assigned_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))


class ItemAnnotationModel(UpdatableTableModel):
    __tablename__ = "item_annotations"

    assessment_item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("assessment_items.id"))
    annotator_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    evaluator_slot: Mapped[int] = mapped_column(SmallInteger)
    single_correct: Mapped[bool | None] = mapped_column(Boolean)
    clear_stem: Mapped[bool | None] = mapped_column(Boolean)
    bloom_ok: Mapped[bool | None] = mapped_column(Boolean)
    plausible_distractors: Mapped[bool | None] = mapped_column(Boolean)
    verdict: Mapped[str] = mapped_column(String(10))
    comment: Mapped[str | None] = mapped_column(Text)


class HumanGradingModel(UpdatableTableModel):
    __tablename__ = "human_gradings"

    attempt_answer_id: Mapped[int] = mapped_column(BigInteger)
    grader_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    sample_type: Mapped[str] = mapped_column(String(20))
    criteria: Mapped[list[Any] | None] = mapped_column(JSONB)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
