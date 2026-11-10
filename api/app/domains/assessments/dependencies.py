"""Composición: repositorios y servicios de evaluaciones, e ingestores para `ai_gateway`."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.ai_gateway.factory import AiServiceDep
from app.domains.ai_gateway.repository import AiServicePort
from app.domains.ai_gateway.service import JobIngestor
from app.domains.assessments.ingestion import (
    DiagnosticFinalizeIngestor,
    QuizBankIngestor,
    ShortAnswerGradingIngestor,
)
from app.domains.assessments.repository_impl import (
    SqlAlchemyAnswerRepository,
    SqlAlchemyAttemptRepository,
    SqlAlchemyBadgeRepository,
    SqlAlchemyContentReader,
    SqlAlchemyDiagnosticRepository,
    SqlAlchemyItemRepository,
)
from app.domains.assessments.service import (
    AttemptService,
    BadgeService,
    DiagnosticService,
    LearnerProgress,
    ProfileRecalculation,
    Repos,
)
from app.domains.learner.repository_impl import SqlAlchemySurveyRepository
from app.domains.learning_paths.repository_impl import (
    SqlAlchemyAlertRepository,
    SqlAlchemyAttemptGrantRepository,
    SqlAlchemyEnrollmentRepository,
    SqlAlchemyPathRepository,
    SqlAlchemyPathStepRepository,
    SqlAlchemyPlatformReader,
)


def build_repos(session: AsyncSession) -> Repos:
    return Repos(
        paths=SqlAlchemyPathRepository(session),
        enrollments=SqlAlchemyEnrollmentRepository(session),
        steps=SqlAlchemyPathStepRepository(session),
        grants=SqlAlchemyAttemptGrantRepository(session),
        alerts=SqlAlchemyAlertRepository(session),
        reader=SqlAlchemyPlatformReader(session),
        items=SqlAlchemyItemRepository(session),
        diagnostics=SqlAlchemyDiagnosticRepository(session),
        attempts=SqlAlchemyAttemptRepository(session),
        answers=SqlAlchemyAnswerRepository(session),
        badges=SqlAlchemyBadgeRepository(session),
        content=SqlAlchemyContentReader(session),
        surveys=SqlAlchemySurveyRepository(session),
    )


def build_ingestors(session: AsyncSession, ai: AiServicePort) -> list[JobIngestor]:
    """Ingestores de `diagnostic.finalize`, `grading.short_answer` e `items.generate_quiz_bank`."""
    repos, uow = build_repos(session), SqlAlchemyUnitOfWork(session)
    attempts = AttemptService(repos, ai, uow)
    return [
        DiagnosticFinalizeIngestor(DiagnosticService(repos, ai, uow)),
        ShortAnswerGradingIngestor(attempts),
        QuizBankIngestor(attempts),
    ]


def build_profile_listener(session: AsyncSession, ai: AiServicePort) -> ProfileRecalculation:
    return ProfileRecalculation(build_repos(session), ai, SqlAlchemyUnitOfWork(session))


def build_progress(session: AsyncSession, ai: AiServicePort) -> LearnerProgress:
    return LearnerProgress(build_repos(session), ai, SqlAlchemyUnitOfWork(session))


def get_diagnostic_service(session: SessionDep, ai: AiServiceDep) -> DiagnosticService:
    return DiagnosticService(build_repos(session), ai, SqlAlchemyUnitOfWork(session))


def get_attempt_service(session: SessionDep, ai: AiServiceDep) -> AttemptService:
    return AttemptService(build_repos(session), ai, SqlAlchemyUnitOfWork(session))


def get_badge_service(session: SessionDep, ai: AiServiceDep) -> BadgeService:
    return BadgeService(build_repos(session), ai, SqlAlchemyUnitOfWork(session))


DiagnosticServiceDep = Annotated[DiagnosticService, Depends(get_diagnostic_service)]
AttemptServiceDep = Annotated[AttemptService, Depends(get_attempt_service)]
BadgeServiceDep = Annotated[BadgeService, Depends(get_badge_service)]
