"""Composición del servicio de trabajos: el registro de ingestores de todos los dominios.

Cada dominio que ingiere resultados de `ai/` registra aquí su ingestor (los agentes posteriores
agregan los de rutas, evaluaciones, contenido y piloto).
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repository_impl import SqlAlchemyUnitOfWork
from app.core.database import SessionDep
from app.domains.ai_gateway.factory import AiServiceDep
from app.domains.ai_gateway.repository import AiServicePort
from app.domains.ai_gateway.service import IngestorRegistry, JobService
from app.domains.courses.ingestion import PublicationIngestor, SyllabusIngestor
from app.domains.courses.repository_impl import (
    SqlAlchemyCourseRepository,
    SqlAlchemyLearningPathRepository,
    SqlAlchemyOutcomeRepository,
    SqlAlchemyPrerequisiteRepository,
    SqlAlchemySyllabusRepository,
    SqlAlchemyTopicRepository,
)


def build_job_service(session: AsyncSession, ai: AiServicePort) -> JobService:
    """Arma el servicio sobre una sesión (la usan la ruta `GET /jobs/{id}` y el barrido)."""
    uow = SqlAlchemyUnitOfWork(session)
    courses = SqlAlchemyCourseRepository(session)
    registry = IngestorRegistry(
        [
            SyllabusIngestor(
                courses,
                SqlAlchemySyllabusRepository(session),
                SqlAlchemyTopicRepository(session),
                SqlAlchemyOutcomeRepository(session),
                SqlAlchemyPrerequisiteRepository(session),
                ai,
                uow,
            ),
            PublicationIngestor(courses, SqlAlchemyLearningPathRepository(session), ai, uow),
        ]
    )
    return JobService(ai, registry)


def get_job_service(session: SessionDep, ai: AiServiceDep) -> JobService:
    return build_job_service(session, ai)


JobServiceDep = Annotated[JobService, Depends(get_job_service)]
