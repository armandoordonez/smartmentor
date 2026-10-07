"""Repositorios SQLAlchemy de cursos."""

from typing import ClassVar

from sqlalchemy import select

from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.courses.entities import Course, Topic, TopicPrerequisite
from app.domains.courses.models import CourseModel, TopicModel, TopicPrerequisiteModel


class SqlAlchemyCourseRepository(SqlAlchemyCrudRepository[CourseModel, Course]):
    model = CourseModel
    entity = Course
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "courses_owner_user_id_fk": ("OWNER_NOT_FOUND", "The owner user does not exist."),
        "courses_status_ck": ("INVALID_COURSE_STATUS", "Invalid course status."),
    }


class SqlAlchemyTopicRepository(SqlAlchemyCrudRepository[TopicModel, Topic]):
    model = TopicModel
    entity = Topic
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "topics_course_id_fk": ("COURSE_NOT_FOUND", "The course does not exist."),
        "topics_bloom_level_ck": ("INVALID_BLOOM_LEVEL", "Invalid Bloom level."),
    }


class SqlAlchemyTopicPrerequisiteRepository(
    SqlAlchemyCrudRepository[TopicPrerequisiteModel, TopicPrerequisite]
):
    model = TopicPrerequisiteModel
    entity = TopicPrerequisite
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "topic_prerequisites_uq": (
            "PREREQUISITE_ALREADY_EXISTS",
            "This prerequisite already exists.",
        ),
        "topic_prerequisites_not_self_ck": (
            "PREREQUISITE_SELF",
            "A topic cannot be its own prerequisite.",
        ),
        "topic_prerequisites_topic_id_fk": ("TOPIC_NOT_FOUND", "The topic does not exist."),
        "topic_prerequisites_prerequisite_topic_id_fk": (
            "PREREQUISITE_TOPIC_NOT_FOUND",
            "The prerequisite topic does not exist.",
        ),
    }

    async def get_prerequisite_ids(self, topic_id: int) -> list[int]:
        result = await self._session.execute(
            select(TopicPrerequisiteModel.prerequisite_topic_id).where(
                TopicPrerequisiteModel.topic_id == topic_id,
                TopicPrerequisiteModel.active.is_(True),
            )
        )
        return list(result.scalars().all())
