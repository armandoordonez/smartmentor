"""Modelos SQLAlchemy de cursos. Reflejan las tablas del esquema v2.0.0 (Liquibase)."""

from typing import Any
from uuid import UUID as PyUUID

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TableModel, UpdatableTableModel


class CourseModel(UpdatableTableModel):
    __tablename__ = "courses"

    owner_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), server_default="draft")
    extraction_error_code: Mapped[str | None] = mapped_column(String(60))


class SyllabusDocumentModel(TableModel):
    __tablename__ = "syllabus_documents"

    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("courses.id"))
    source_type: Mapped[str] = mapped_column(String(10))
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    extracted_char_count: Mapped[int] = mapped_column(Integer)
    extracted_text: Mapped[str] = mapped_column(Text)


class SyllabusExtractionModel(TableModel):
    __tablename__ = "syllabus_extractions"

    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("courses.id"))
    syllabus_document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("syllabus_documents.id")
    )
    ai_job_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True))
    raw_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    prompt_version: Mapped[str | None] = mapped_column(String(60))
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class TopicModel(UpdatableTableModel):
    __tablename__ = "topics"

    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("courses.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    subtopics: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    position: Mapped[int] = mapped_column(Integer, server_default="0")
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    bloom_level: Mapped[str | None] = mapped_column(String(20))
    origin: Mapped[str] = mapped_column(String(20), server_default="instructor")
    review_status: Mapped[str] = mapped_column(String(20), server_default="unchanged")
    extraction_key: Mapped[str | None] = mapped_column(String(100))


class LearningOutcomeModel(TableModel):
    __tablename__ = "learning_outcomes"

    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"))
    code: Mapped[str] = mapped_column(String(100))
    statement: Mapped[str] = mapped_column(Text)
    bloom_level: Mapped[str] = mapped_column(String(20))


class TopicPrerequisiteModel(TableModel):
    __tablename__ = "topic_prerequisites"

    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"))
    prerequisite_topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("topics.id"))
    origin: Mapped[str] = mapped_column(String(20), server_default="instructor")
