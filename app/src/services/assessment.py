"""Quiz del tema (E6, E7), evaluación final (E8), repaso dirigido (E9), badge (E10) y logros (E12).

La calificación, los umbrales y los intentos los decide la API; la interfaz solo entrega las
respuestas y muestra el resultado.
"""

from dataclasses import dataclass

from clients.base import Answers, SmartMentorClient
from clients.models import (
    Badge,
    Enrollment,
    FinalAssessment,
    FinalResult,
    LearningPath,
    QuizResult,
)
from services.catalog import active_enrollment


@dataclass(frozen=True)
class BadgeSlot:
    path: LearningPath
    badge: Badge | None
    enrolled: bool


class AssessmentService:
    def __init__(self, client: SmartMentorClient) -> None:
        self._client = client

    def submit_quiz(self, enrollment_id: int, topic_id: int, answers: Answers) -> QuizResult:
        return self._client.submit_topic_quiz(enrollment_id, topic_id, answers)

    def final_assessment(self, enrollment_id: int) -> FinalAssessment:
        return self._client.get_final_assessment(enrollment_id)

    def submit_final(self, enrollment_id: int, answers: Answers) -> FinalResult:
        return self._client.submit_final_assessment(enrollment_id, answers)

    def last_final_result(self, enrollment_id: int) -> FinalResult | None:
        results = self._client.list_final_results(enrollment_id)
        return results[-1] if results else None

    def badge_for(self, enrollment: Enrollment) -> Badge | None:
        return next(
            (b for b in self._client.list_my_badges() if b.enrollment_id == enrollment.id), None
        )

    def badge_slots(self) -> list[BadgeSlot]:
        badges = {b.learning_path_id: b for b in self._client.list_my_badges()}
        enrollments = self._client.list_my_enrollments()
        paths = {p.id: p for p in self._client.list_learning_paths()}
        # Una ruta con badge puede haber dejado de publicarse; el badge sigue siendo del estudiante.
        for path_id in badges.keys() - paths.keys():
            paths[path_id] = self._client.get_learning_path(path_id)
        slots = [
            BadgeSlot(
                path=path,
                badge=badges.get(path.id),
                enrolled=active_enrollment(enrollments, path.id) is not None,
            )
            for path in paths.values()
        ]
        return sorted(slots, key=lambda s: (s.badge is None, s.path.title))
