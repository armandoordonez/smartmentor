"""Interfaces (puertos) de la encuesta y los eventos del aprendiz."""

from typing import Protocol

from app.domains.learner.entities import InteractionEvent, SurveyResponse


class SurveyRepository(Protocol):
    async def add(self, response: SurveyResponse) -> SurveyResponse: ...

    async def has_final_survey(self, enrollment_id: int) -> bool: ...


class EventRepository(Protocol):
    async def add_many(self, events: list[InteractionEvent]) -> int:
        """Inserta los eventos y devuelve cuántos guardó."""
        ...
