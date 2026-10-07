"""Composición: construye los servicios de rutas con sus repositorios SQLAlchemy."""

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.courses.repository_impl import SqlAlchemyTopicRepository
from app.domains.learning_paths.repository_impl import (
    SqlAlchemyEnrollmentRepository,
    SqlAlchemyLearningPathRepository,
    SqlAlchemyPathStepRepository,
)
from app.domains.learning_paths.service import (
    EnrollmentService,
    LearningPathService,
    PathStepService,
)


def get_learning_path_service(session: SessionDep) -> LearningPathService:
    return LearningPathService(
        SqlAlchemyLearningPathRepository(session), SqlAlchemyUnitOfWork(session)
    )


def get_enrollment_service(session: SessionDep) -> EnrollmentService:
    return EnrollmentService(SqlAlchemyEnrollmentRepository(session), SqlAlchemyUnitOfWork(session))


def get_path_step_service(session: SessionDep) -> PathStepService:
    return PathStepService(
        SqlAlchemyPathStepRepository(session),
        SqlAlchemyEnrollmentRepository(session),
        SqlAlchemyLearningPathRepository(session),
        SqlAlchemyTopicRepository(session),
        SqlAlchemyUnitOfWork(session),
    )
