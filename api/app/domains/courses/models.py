"""Modelos SQLAlchemy de cursos. Reflejan courses, topics y topic_prerequisites de Liquibase."""

from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TableModel
from app.core.config import get_settings


class CourseModel(TableModel):
    __tablename__ = "courses"

    owner_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    raw_syllabus: Mapped[str | None] = mapped_column(Text)
    syllabus_file_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), server_default="draft")


class TopicModel(TableModel):
    __tablename__ = "topics"

    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("courses.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    learning_outcomes: Mapped[list[Any]] = mapped_column(JSONB, server_default="[]")
    bloom_level: Mapped[str | None] = mapped_column(String(20))
    # Dimensión provisional (pendiente D-01): debe coincidir con el esquema de Liquibase.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(get_settings().embedding_dimension)
    )


class TopicPrerequisiteModel(TableModel):
    __tablename__ = "topic_prerequisites"

    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"))
    prerequisite_topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"))
