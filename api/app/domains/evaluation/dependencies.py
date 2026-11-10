"""Composición: servicios de evaluación humana con sus repositorios SQLAlchemy."""

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.content.repository_impl import SqlAlchemyItemRepository
from app.domains.courses.repository_impl import (
    SqlAlchemyCourseRepository,
    SqlAlchemyTopicRepository,
)
from app.domains.evaluation.repository_impl import (
    SqlAlchemyAnnotationRepository,
    SqlAlchemyEvaluatorRepository,
    SqlAlchemyGradingRepository,
)
from app.domains.evaluation.service import (
    AnnotationService,
    EvaluatorAccess,
    EvaluatorAdminService,
    GradingService,
)


def get_evaluator_admin_service(session: SessionDep) -> EvaluatorAdminService:
    return EvaluatorAdminService(
        SqlAlchemyEvaluatorRepository(session),
        SqlAlchemyCourseRepository(session),
        SqlAlchemyUnitOfWork(session),
    )


def get_annotation_service(session: SessionDep) -> AnnotationService:
    return AnnotationService(
        EvaluatorAccess(SqlAlchemyEvaluatorRepository(session)),
        SqlAlchemyAnnotationRepository(session),
        SqlAlchemyItemRepository(session),
        SqlAlchemyTopicRepository(session),
        SqlAlchemyCourseRepository(session),
        SqlAlchemyUnitOfWork(session),
    )


def get_grading_service(session: SessionDep) -> GradingService:
    return GradingService(
        EvaluatorAccess(SqlAlchemyEvaluatorRepository(session)),
        SqlAlchemyGradingRepository(session),
        SqlAlchemyUnitOfWork(session),
    )
