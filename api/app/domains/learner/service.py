"""Casos de uso del aprendiz: encuesta final con SUS (E13a, E13b) y eventos de tiempo en tarea."""

from collections.abc import Mapping
from typing import Any

from app.common.exceptions import ConflictError, InvalidStateTransitionError
from app.common.unit_of_work import UnitOfWork
from app.domains.assessments.grading import sus_score
from app.domains.identity.authentication import CurrentUser
from app.domains.learner.entities import InteractionEvent, SurveyResponse
from app.domains.learner.repository import EventRepository, SurveyRepository
from app.domains.learning_paths import exceptions as path_errors
from app.domains.learning_paths.entities import Enrollment
from app.domains.learning_paths.repository import EnrollmentRepository
from app.domains.learning_paths.states import EnrollmentStatus


async def _own(enrollments: EnrollmentRepository, user: CurrentUser, enrollment_id: int) -> Enrollment:
    enrollment = await enrollments.get(enrollment_id)
    if enrollment is None or enrollment.user_id != user.id or not enrollment.active:
        raise path_errors.enrollment_not_found(enrollment_id)
    return enrollment


class SurveyService:
    def __init__(
        self, enrollments: EnrollmentRepository, surveys: SurveyRepository, uow: UnitOfWork
    ) -> None:
        self._enrollments = enrollments
        self._surveys = surveys
        self._uow = uow

    async def submit_final(
        self,
        user: CurrentUser,
        enrollment_id: int,
        *,
        likert: Mapping[str, Any],
        sus_items: list[int],
        comment: str | None,
    ) -> SurveyResponse:
        """Encuesta final: se responde con la ruta completada y calcula `sus_score`."""
        enrollment = await _own(self._enrollments, user, enrollment_id)
        if enrollment.status != EnrollmentStatus.COMPLETED:
            raise InvalidStateTransitionError("The final survey opens when the path is completed.")
        if await self._surveys.has_final_survey(enrollment_id):
            raise ConflictError(
                "The final survey was already submitted.", code="SURVEY_ALREADY_SUBMITTED"
            )
        score = sus_score(sus_items)
        created = await self._surveys.add(
            SurveyResponse(
                enrollment_id=enrollment_id,
                likert=dict(likert),
                sus_items=list(sus_items),
                sus_score=score,
                comment=comment,
            )
        )
        await self._uow.commit()
        return created


class EventService:
    def __init__(
        self, enrollments: EnrollmentRepository, events: EventRepository, uow: UnitOfWork
    ) -> None:
        self._enrollments = enrollments
        self._events = events
        self._uow = uow

    async def record(self, user: CurrentUser, events: list[InteractionEvent]) -> int:
        """Guarda un lote de eventos; todos deben ser de inscripciones del aprendiz."""
        for enrollment_id in sorted({e.enrollment_id for e in events}):
            await _own(self._enrollments, user, enrollment_id)
        saved = await self._events.add_many(events)
        await self._uow.commit()
        return saved
