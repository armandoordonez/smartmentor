"""Composición: construye los servicios de cursos con sus repositorios SQLAlchemy."""

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.courses.repository_impl import (
    SqlAlchemyCourseRepository,
    SqlAlchemyTopicPrerequisiteRepository,
    SqlAlchemyTopicRepository,
)
from app.domains.courses.service import CourseService, TopicPrerequisiteService, TopicService


def get_course_service(session: SessionDep) -> CourseService:
    return CourseService(SqlAlchemyCourseRepository(session), SqlAlchemyUnitOfWork(session))


def get_topic_service(session: SessionDep) -> TopicService:
    return TopicService(SqlAlchemyTopicRepository(session), SqlAlchemyUnitOfWork(session))


def get_topic_prerequisite_service(session: SessionDep) -> TopicPrerequisiteService:
    return TopicPrerequisiteService(
        SqlAlchemyTopicPrerequisiteRepository(session),
        SqlAlchemyTopicRepository(session),
        SqlAlchemyUnitOfWork(session),
    )
