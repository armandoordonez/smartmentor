"""Repositorios SQLAlchemy de la encuesta y los eventos del aprendiz."""

import json
from typing import ClassVar

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ReferenceNotFoundError
from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.learner.entities import InteractionEvent, SurveyResponse
from app.domains.learner.models import SurveyResponseModel


class SqlAlchemySurveyRepository(SqlAlchemyCrudRepository[SurveyResponseModel, SurveyResponse]):
    model = SurveyResponseModel
    entity = SurveyResponse
    constraint_messages: ClassVar[dict[str, tuple[str, str]]] = {
        "survey_responses_enrollment_type_uq": (
            "SURVEY_ALREADY_SUBMITTED",
            "The final survey was already submitted.",
        ),
    }

    async def has_final_survey(self, enrollment_id: int) -> bool:
        found = await self._session.execute(
            select(SurveyResponseModel.id)
            .where(
                SurveyResponseModel.enrollment_id == enrollment_id,
                SurveyResponseModel.survey_type == "final",
            )
            .limit(1)
        )
        return found.first() is not None


class SqlAlchemyEventRepository:
    """`interaction_events` es de solo inserción (sin `_audit`, plan 5.2.1): SQL explícito."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_many(self, events: list[InteractionEvent]) -> int:
        if not events:
            return 0
        try:
            await self._session.execute(
                text(
                    "INSERT INTO interaction_events "
                    "(enrollment_id, event_type, topic_id, occurred_at, payload) "
                    "VALUES (:enrollment_id, :event_type, :topic_id, :occurred_at, "
                    "CAST(:payload AS jsonb))"
                ),
                [
                    {
                        "enrollment_id": e.enrollment_id,
                        "event_type": e.event_type,
                        "topic_id": e.topic_id,
                        "occurred_at": e.occurred_at,
                        "payload": None if e.payload is None else json.dumps(e.payload),
                    }
                    for e in events
                ],
            )
        except IntegrityError as exc:
            raise ReferenceNotFoundError("A referenced topic does not exist.") from exc
        return len(events)
