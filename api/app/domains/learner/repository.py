"""Interfaces (puertos) de la encuesta y los eventos del aprendiz."""

from typing import Protocol

from app.domains.learner.entities import InteractionEvent, StudyGoals, SurveyResponse


class SurveyRepository(Protocol):
    async def add(self, response: SurveyResponse) -> SurveyResponse: ...

    async def has_final_survey(self, enrollment_id: int) -> bool: ...


class EventRepository(Protocol):
    async def add_many(self, events: list[InteractionEvent]) -> int:
        """Inserta los eventos y devuelve cuántos guardó."""
        ...


class StudyGoalRepository(Protocol):
    async def get(self, user_id: int) -> tuple[int, int] | None:
        """(minutos al día, temas al mes) o `None` si el aprendiz no definió metas."""
        ...

    async def save(self, user_id: int, daily_minutes: int, monthly_topics: int) -> None: ...

    async def progress(self, user_id: int, goals: tuple[int, int]) -> StudyGoals:
        """Minutos de hoy, temas aprobados este mes y días seguidos con actividad."""
        ...
