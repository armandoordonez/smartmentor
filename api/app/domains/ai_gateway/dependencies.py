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
from app.domains.ai_gateway.service import IngestorRegistry, JobIngestor, JobService
from app.domains.assessments.dependencies import build_ingestors
from app.domains.content.constants import ContentJobType
from app.domains.content.ingestion import (
    ExplanationIngestor,
    FaithfulnessIngestor,
    ItemBankIngestor,
    ItemReviewIngestor,
    VideoIngestor,
)
from app.domains.content.repository_impl import (
    SqlAlchemyItemRepository,
    SqlAlchemyResourceRepository,
    SqlAlchemyVideoRepository,
)
from app.domains.courses.ingestion import PublicationIngestor, SyllabusIngestor
from app.domains.courses.repository_impl import (
    SqlAlchemyCourseRepository,
    SqlAlchemyLearningPathRepository,
    SqlAlchemyOutcomeRepository,
    SqlAlchemyPrerequisiteRepository,
    SqlAlchemySyllabusRepository,
    SqlAlchemyTopicRepository,
)


def _content_ingestors(session: AsyncSession, ai: AiServicePort) -> list[JobIngestor]:
    """Ingestores de contenido: explicaciones, bancos de ítems, revisión y videos."""
    uow = SqlAlchemyUnitOfWork(session)
    courses = SqlAlchemyCourseRepository(session)
    topics = SqlAlchemyTopicRepository(session)
    resources = SqlAlchemyResourceRepository(session)
    items = SqlAlchemyItemRepository(session)
    banks = [
        (ContentJobType.DIAGNOSTIC_BANK, "Armando el banco del diagnóstico"),
        (ContentJobType.QUIZ_BANK, "Armando el banco de preguntas del tema"),
        (ContentJobType.FINAL_BANK, "Armando el banco de la evaluación final"),
    ]
    return [
        ExplanationIngestor(courses, topics, resources, ai, uow),
        FaithfulnessIngestor(courses, topics, resources, ai, uow),
        ItemReviewIngestor(courses, topics, items, ai, uow),
        VideoIngestor(courses, topics, SqlAlchemyVideoRepository(session), resources, ai, uow),
        *[ItemBankIngestor(t, label, courses, topics, items, ai, uow) for t, label in banks],
    ]


def build_job_service(session: AsyncSession, ai: AiServicePort) -> JobService:
    """Arma el servicio sobre una sesión (la usan la ruta `GET /jobs/{id}` y el barrido)."""
    uow = SqlAlchemyUnitOfWork(session)
    courses = SqlAlchemyCourseRepository(session)
    content = _content_ingestors(session, ai)
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
            *content,
            # Van después: el banco del quiz pedido por un aprendiz (U1b) lo ingiere `assessments`
            # y delega en el de contenido los bancos generados al publicar el curso.
            *build_ingestors(session, ai, content),
        ]
    )
    return JobService(ai, registry)


def get_job_service(session: SessionDep, ai: AiServiceDep) -> JobService:
    return build_job_service(session, ai)


JobServiceDep = Annotated[JobService, Depends(get_job_service)]
