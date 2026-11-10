"""Composición: encuesta y eventos del aprendiz."""

from typing import Annotated

from fastapi import Depends

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.learner.repository_impl import SqlAlchemyEventRepository, SqlAlchemySurveyRepository
from app.domains.learner.service import EventService, SurveyService
from app.domains.learning_paths.repository_impl import SqlAlchemyEnrollmentRepository


def get_survey_service(session: SessionDep) -> SurveyService:
    return SurveyService(
        SqlAlchemyEnrollmentRepository(session),
        SqlAlchemySurveyRepository(session),
        SqlAlchemyUnitOfWork(session),
    )


def get_event_service(session: SessionDep) -> EventService:
    return EventService(
        SqlAlchemyEnrollmentRepository(session),
        SqlAlchemyEventRepository(session),
        SqlAlchemyUnitOfWork(session),
    )


SurveyServiceDep = Annotated[SurveyService, Depends(get_survey_service)]
EventServiceDep = Annotated[EventService, Depends(get_event_service)]
