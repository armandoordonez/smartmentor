"""Contratos HTTP de cursos."""

from typing import Any

from pydantic import Field, field_validator

from app.common.constants import BloomLevel, CourseStatus
from app.common.schemas import RequestSchema, ResponseSchema
from app.core.config import get_settings


def validate_embedding(value: list[float] | None) -> list[float] | None:
    expected = get_settings().embedding_dimension
    if value is not None and len(value) != expected:
        raise ValueError(f"embedding must have {expected} dimensions, got {len(value)}")
    return value


class CourseCreate(RequestSchema):
    owner_user_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    raw_syllabus: str | None = None
    syllabus_file_path: str | None = Field(default=None, max_length=500)
    status: CourseStatus = CourseStatus.DRAFT


class CourseUpdate(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    raw_syllabus: str | None = None
    syllabus_file_path: str | None = Field(default=None, max_length=500)
    status: CourseStatus | None = None


class CourseResponse(ResponseSchema):
    owner_user_id: int
    name: str
    description: str | None
    raw_syllabus: str | None
    syllabus_file_path: str | None
    status: str


class TopicCreate(RequestSchema):
    course_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    learning_outcomes: list[Any] = Field(default_factory=list)
    bloom_level: BloomLevel | None = None
    embedding: list[float] | None = None

    _check_embedding = field_validator("embedding")(validate_embedding)


class TopicUpdate(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    learning_outcomes: list[Any] | None = None
    bloom_level: BloomLevel | None = None
    embedding: list[float] | None = None

    _check_embedding = field_validator("embedding")(validate_embedding)


class TopicResponse(ResponseSchema):
    """El embedding no se devuelve: es grande y solo lo usa la capa de IA."""

    course_id: int
    name: str
    description: str | None
    learning_outcomes: list[Any]
    bloom_level: str | None
    has_embedding: bool


class TopicPrerequisiteCreate(RequestSchema):
    topic_id: int = Field(gt=0)
    prerequisite_topic_id: int = Field(gt=0)


class TopicPrerequisiteUpdate(RequestSchema):
    """Un prerrequisito no tiene campos editables: se activa o se inactiva."""


class TopicPrerequisiteResponse(ResponseSchema):
    topic_id: int
    prerequisite_topic_id: int
