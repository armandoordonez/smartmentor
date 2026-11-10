"""Repositorios SQLAlchemy de la encuesta y los eventos del aprendiz."""

import json
from datetime import date, timedelta
from typing import ClassVar

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import ReferenceNotFoundError
from app.common.repository_impl import SqlAlchemyCrudRepository
from app.domains.learner.entities import InteractionEvent, StudyGoals, SurveyResponse
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


class SqlAlchemyStudyGoalRepository:
    """`study_goals` (P2) y el avance que se calcula con `interaction_events` y `path_steps`.

    SQL explícito: una fila por aprendiz (`study_goals_user_id_uq`) y lecturas agregadas.
    """

    def __init__(self, session: AsyncSession, timezone: str) -> None:
        self._session = session
        self._tz = timezone

    async def get(self, user_id: int) -> tuple[int, int] | None:
        row = (
            await self._session.execute(
                text(
                    "SELECT daily_minutes, monthly_topics FROM study_goals "
                    "WHERE user_id = :user_id AND active"
                ),
                {"user_id": user_id},
            )
        ).first()
        if row is None or row[0] is None or row[1] is None:
            return None
        return int(row[0]), int(row[1])

    async def save(self, user_id: int, daily_minutes: int, monthly_topics: int) -> None:
        await self._session.execute(
            text(
                "INSERT INTO study_goals (user_id, daily_minutes, monthly_topics) "
                "VALUES (:user_id, :daily, :monthly) ON CONFLICT (user_id) DO UPDATE "
                "SET daily_minutes = EXCLUDED.daily_minutes, "
                "monthly_topics = EXCLUDED.monthly_topics, active = true"
            ),
            {"user_id": user_id, "daily": daily_minutes, "monthly": monthly_topics},
        )

    async def progress(self, user_id: int, goals: tuple[int, int]) -> StudyGoals:
        params = {"user_id": user_id, "tz": self._tz}
        seconds = (
            await self._session.execute(
                text(
                    "SELECT coalesce(sum((ev.payload ->> 'seconds')::numeric), 0) "
                    "FROM interaction_events ev JOIN enrollments e ON e.id = ev.enrollment_id "
                    "WHERE e.user_id = :user_id "
                    "AND jsonb_typeof(ev.payload -> 'seconds') = 'number' "
                    "AND (ev.occurred_at AT TIME ZONE :tz)::date = (now() AT TIME ZONE :tz)::date"
                ),
                params,
            )
        ).scalar_one()
        topics = (
            await self._session.execute(
                text(
                    "SELECT count(*) FROM path_steps s "
                    "JOIN enrollments e ON e.id = s.enrollment_id "
                    "WHERE e.user_id = :user_id AND s.status = 'passed' "
                    "AND date_trunc('month', s.updated_at AT TIME ZONE :tz) "
                    "= date_trunc('month', now() AT TIME ZONE :tz)"
                ),
                params,
            )
        ).scalar_one()
        days = (
            await self._session.execute(
                text(
                    "SELECT DISTINCT (ev.occurred_at AT TIME ZONE :tz)::date AS day, "
                    "(now() AT TIME ZONE :tz)::date AS today "
                    "FROM interaction_events ev JOIN enrollments e ON e.id = ev.enrollment_id "
                    "WHERE e.user_id = :user_id ORDER BY day DESC LIMIT 400"
                ),
                params,
            )
        ).all()
        return StudyGoals(
            daily_minutes_goal=goals[0],
            monthly_topics_goal=goals[1],
            daily_minutes_done=round(float(seconds) / 60),
            monthly_topics_done=int(topics),
            streak_days=_streak([d[0] for d in days], days[0][1] if days else None),
        )


def _streak(days: list[date], today: date | None) -> int:
    """Días seguidos con actividad que terminan hoy o ayer."""
    if not days or today is None:
        return 0
    active = set(days)
    cursor = today if today in active else today - timedelta(days=1)
    streak = 0
    while cursor in active:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
