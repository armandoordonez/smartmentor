"""Entidades del dominio de cursos (Python puro)."""

from dataclasses import dataclass, field
from typing import Any

from app.common.entities import BaseEntity


@dataclass(kw_only=True)
class Course(BaseEntity):
    owner_user_id: int
    name: str
    description: str | None = None
    raw_syllabus: str | None = None
    syllabus_file_path: str | None = None
    status: str = "draft"


@dataclass(kw_only=True)
class Topic(BaseEntity):
    course_id: int
    name: str
    description: str | None = None
    learning_outcomes: list[Any] = field(default_factory=list)
    bloom_level: str | None = None
    embedding: list[float] | None = None

    @property
    def has_embedding(self) -> bool:
        return self.embedding is not None


@dataclass(kw_only=True)
class TopicPrerequisite(BaseEntity):
    topic_id: int
    prerequisite_topic_id: int
