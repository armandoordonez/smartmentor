"""Entidades del dominio de cursos (Python puro)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.common.entities import BaseEntity


@dataclass(kw_only=True)
class Course(BaseEntity):
    owner_user_id: int | None = None  # nulo = «Sin asignar» (AD5)
    name: str
    description: str | None = None
    status: str = "draft"
    extraction_error_code: str | None = None
    updated_at: datetime | None = None


@dataclass(kw_only=True)
class SyllabusDocument(BaseEntity):
    course_id: int
    source_type: str
    file_name: str | None = None
    file_sha256: str
    byte_size: int
    page_count: int | None = None
    extracted_char_count: int
    extracted_text: str


@dataclass(kw_only=True)
class SyllabusExtraction(BaseEntity):
    course_id: int
    syllabus_document_id: int
    raw_output: dict[str, Any]
    ai_job_id: int | None = None  # id interno de `ai_jobs` (nulo si no se pudo resolver)
    prompt_version: str | None = None
    is_current: bool = True


@dataclass(kw_only=True)
class Topic(BaseEntity):
    course_id: int
    name: str
    description: str | None = None
    subtopics: list[Any] = field(default_factory=list)
    position: int = 0
    estimated_minutes: int | None = None
    is_mandatory: bool = False
    bloom_level: str | None = None
    origin: str = "instructor"
    review_status: str = "unchanged"
    extraction_key: str | None = None
    updated_at: datetime | None = None


@dataclass(kw_only=True)
class LearningOutcome(BaseEntity):
    topic_id: int
    code: str
    statement: str
    bloom_level: str


@dataclass(kw_only=True)
class TopicPrerequisite(BaseEntity):
    topic_id: int
    prerequisite_topic_id: int
    origin: str = "instructor"
