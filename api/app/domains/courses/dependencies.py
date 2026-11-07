"""Composición: servicios de cursos con sus repositorios SQLAlchemy."""

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.ai_gateway.factory import AiServiceDep
from app.domains.courses.repository_impl import (
    SqlAlchemyCourseRepository,
    SqlAlchemyLearningPathRepository,
    SqlAlchemyOutcomeRepository,
    SqlAlchemyPrerequisiteRepository,
    SqlAlchemySyllabusRepository,
    SqlAlchemyTopicRepository,
)
from app.domains.courses.service import (
    CourseService,
    PublicationService,
    SyllabusService,
    TopicService,
)
from app.domains.identity.repository_impl import SqlAlchemyUserRepository


def get_course_service(session: SessionDep) -> CourseService:
    return CourseService(
        SqlAlchemyCourseRepository(session),
        SqlAlchemyLearningPathRepository(session),
        SqlAlchemySyllabusRepository(session),
        SqlAlchemyUserRepository(session),
        SqlAlchemyUnitOfWork(session),
    )


def get_syllabus_service(session: SessionDep, ai: AiServiceDep) -> SyllabusService:
    return SyllabusService(
        SqlAlchemyCourseRepository(session),
        SqlAlchemySyllabusRepository(session),
        SqlAlchemyTopicRepository(session),
        SqlAlchemyPrerequisiteRepository(session),
        ai,
        SqlAlchemyUnitOfWork(session),
    )


def get_topic_service(session: SessionDep) -> TopicService:
    return TopicService(
        SqlAlchemyCourseRepository(session),
        SqlAlchemyTopicRepository(session),
        SqlAlchemyOutcomeRepository(session),
        SqlAlchemyPrerequisiteRepository(session),
        SqlAlchemyUnitOfWork(session),
    )


def get_publication_service(session: SessionDep, ai: AiServiceDep) -> PublicationService:
    return PublicationService(
        SqlAlchemyCourseRepository(session),
        SqlAlchemyLearningPathRepository(session),
        SqlAlchemyTopicRepository(session),
        SqlAlchemyOutcomeRepository(session),
        SqlAlchemyPrerequisiteRepository(session),
        ai,
        SqlAlchemyUnitOfWork(session),
    )
