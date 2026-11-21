"""Composición: servicios de observabilidad con sus repositorios SQLAlchemy."""

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.ai_gateway.factory import AiServiceDep
from app.domains.courses.repository_impl import (
    SqlAlchemyCourseRepository,
    SqlAlchemyPrerequisiteRepository,
    SqlAlchemySyllabusRepository,
    SqlAlchemyTopicRepository,
)
from app.domains.courses.service import SyllabusService
from app.domains.observability.repository_impl import SqlAlchemyObservabilityRepository
from app.domains.observability.service import LogService, MetricsService


def get_log_service(session: SessionDep) -> LogService:
    return LogService(SqlAlchemyObservabilityRepository(session))


def get_metrics_service(session: SessionDep, ai: AiServiceDep) -> MetricsService:
    syllabus = SyllabusService(
        SqlAlchemyCourseRepository(session),
        SqlAlchemySyllabusRepository(session),
        SqlAlchemyTopicRepository(session),
        SqlAlchemyPrerequisiteRepository(session),
        ai,
        SqlAlchemyUnitOfWork(session),
    )
    return MetricsService(SqlAlchemyObservabilityRepository(session), syllabus)
