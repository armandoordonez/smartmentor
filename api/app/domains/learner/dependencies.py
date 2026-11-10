"""Composición: encuesta y eventos del aprendiz."""

from typing import Annotated

from fastapi import Depends

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.config import get_settings
from app.core.database import SessionDep
from app.domains.learner.repository_impl import (
    SqlAlchemyEventRepository,
    SqlAlchemyStudyGoalRepository,
    SqlAlchemySurveyRepository,
)
from app.domains.learner.service import EventService, StudyGoalService, SurveyService
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


def get_study_goal_service(session: SessionDep) -> StudyGoalService:
    return StudyGoalService(
        SqlAlchemyStudyGoalRepository(session, get_settings().app_timezone),
        SqlAlchemyUnitOfWork(session),
    )


StudyGoalServiceDep = Annotated[StudyGoalService, Depends(get_study_goal_service)]
SurveyServiceDep = Annotated[SurveyService, Depends(get_survey_service)]
EventServiceDep = Annotated[EventService, Depends(get_event_service)]
