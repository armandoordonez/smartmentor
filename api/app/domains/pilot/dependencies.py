"""Composición: servicio del piloto con sus repositorios SQLAlchemy."""

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.ai_gateway.factory import AiServiceDep
from app.domains.courses.repository_impl import (
    SqlAlchemyPrerequisiteRepository,
    SqlAlchemyTopicRepository,
)
from app.domains.pilot.repository_impl import SqlAlchemyPilotPopulation, SqlAlchemyPilotRepository
from app.domains.pilot.service import PilotService


def get_pilot_service(session: SessionDep, ai: AiServiceDep) -> PilotService:
    return PilotService(
        SqlAlchemyPilotRepository(session),
        SqlAlchemyPilotPopulation(session),
        SqlAlchemyTopicRepository(session),
        SqlAlchemyPrerequisiteRepository(session),
        ai,
        SqlAlchemyUnitOfWork(session),
    )
