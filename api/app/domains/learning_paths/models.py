"""Modelos SQLAlchemy de rutas: learning_paths, enrollments y path_steps de Liquibase."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, ForeignKey, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TableModel
from app.core.config import get_settings


class LearningPathModel(TableModel):
    __tablename__ = "learning_paths"

    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("courses.id"))
    name: Mapped[str] = mapped_column(String(200))
    default_objective: Mapped[str | None] = mapped_column(Text)
    topic_pass_threshold: Mapped[float] = mapped_column(Numeric(5, 2), server_default="70")
    final_pass_threshold: Mapped[float] = mapped_column(Numeric(5, 2), server_default="80")
    mastery_skip_threshold: Mapped[float] = mapped_column(Numeric(5, 2), server_default="80")
    max_attempts: Mapped[int] = mapped_column(SmallInteger, server_default="3")


class EnrollmentModel(TableModel):
    __tablename__ = "enrollments"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    learning_path_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_paths.id"))
    profile_description: Mapped[str | None] = mapped_column(Text)
    # Dimensión provisional (pendiente D-01): debe coincidir con el esquema de Liquibase.
    profile_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(get_settings().embedding_dimension)
    )
    personal_objective: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), server_default="enrolled")


class PathStepModel(TableModel):
    __tablename__ = "path_steps"

    enrollment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("enrollments.id"))
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"))
    step_order: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    score: Mapped[float | None] = mapped_column(Numeric(5, 2))
