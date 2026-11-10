"""Composición: servicios de contenido con sus repositorios SQLAlchemy."""

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.ai_gateway.factory import AiServiceDep
from app.domains.content.repository_impl import (
    SqlAlchemyEnrollmentLookup,
    SqlAlchemyFeedbackRepository,
    SqlAlchemyItemRepository,
    SqlAlchemyResourceRepository,
    SqlAlchemyVideoRepository,
)
from app.domains.content.service import (
    ItemService,
    ResourceService,
    VideoFeedbackService,
    VideoService,
)
from app.domains.courses.repository_impl import (
    SqlAlchemyCourseRepository,
    SqlAlchemyLearningPathRepository,
    SqlAlchemyTopicRepository,
)


def get_resource_service(session: SessionDep, ai: AiServiceDep) -> ResourceService:
    return ResourceService(
        SqlAlchemyResourceRepository(session),
        SqlAlchemyTopicRepository(session),
        SqlAlchemyCourseRepository(session),
        ai,
        SqlAlchemyUnitOfWork(session),
    )


def get_item_service(session: SessionDep, ai: AiServiceDep) -> ItemService:
    return ItemService(
        SqlAlchemyItemRepository(session),
        SqlAlchemyTopicRepository(session),
        SqlAlchemyCourseRepository(session),
        ai,
        SqlAlchemyUnitOfWork(session),
    )


def get_video_service(session: SessionDep) -> VideoService:
    return VideoService(
        SqlAlchemyVideoRepository(session),
        SqlAlchemyResourceRepository(session),
        SqlAlchemyTopicRepository(session),
        SqlAlchemyCourseRepository(session),
        SqlAlchemyLearningPathRepository(session),
        SqlAlchemyFeedbackRepository(session),
        SqlAlchemyUnitOfWork(session),
    )


def get_video_feedback_service(session: SessionDep) -> VideoFeedbackService:
    return VideoFeedbackService(
        SqlAlchemyVideoRepository(session),
        SqlAlchemyFeedbackRepository(session),
        SqlAlchemyTopicRepository(session),
        SqlAlchemyEnrollmentLookup(session),
        SqlAlchemyUnitOfWork(session),
    )
