"""Composición: servicios de rutas, sus repositorios y los puertos que implementa `assessments`."""

from typing import Annotated

from fastapi import Depends

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.ai_gateway.factory import AiServiceDep
from app.domains.assessments.dependencies import build_progress, build_repos
from app.domains.learning_paths.service import EnrollmentService, PathProgress, PathStaffService


def get_enrollment_service(session: SessionDep, ai: AiServiceDep) -> EnrollmentService:
    repos = build_repos(session)
    return EnrollmentService(
        repos.paths,
        repos.enrollments,
        repos.steps,
        repos.reader,
        build_progress(session, ai),
        SqlAlchemyUnitOfWork(session),
    )


def get_path_staff_service(session: SessionDep, ai: AiServiceDep) -> PathStaffService:
    repos = build_repos(session)
    return PathStaffService(
        repos.paths,
        repos.enrollments,
        repos.steps,
        repos.grants,
        repos.alerts,
        repos.reader,
        PathProgress(repos.enrollments, repos.steps, repos.alerts, repos.reader, ai),
        build_progress(session, ai),
        SqlAlchemyUnitOfWork(session),
    )


EnrollmentServiceDep = Annotated[EnrollmentService, Depends(get_enrollment_service)]
PathStaffServiceDep = Annotated[PathStaffService, Depends(get_path_staff_service)]
