"""Interfaces (puertos) de los repositorios de cursos."""

from typing import Protocol

from app.common.repository import CrudRepository
from app.domains.courses.entities import Course, Topic, TopicPrerequisite


class CourseRepository(CrudRepository[Course], Protocol): ...


class TopicRepository(CrudRepository[Topic], Protocol): ...


class TopicPrerequisiteRepository(CrudRepository[TopicPrerequisite], Protocol):
    async def get_prerequisite_ids(self, topic_id: int) -> list[int]:
        """Ids de los temas que son prerrequisito directo (activo) del tema dado."""
        ...
