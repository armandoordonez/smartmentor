"""Inscripción y punto de partida (E2 perfil, E3 diagnóstico, E4 resultado y objetivo)."""

from clients.base import Answers, SmartMentorClient
from clients.models import Diagnostic, Enrollment
from services.catalog import active_enrollment


class EnrollmentService:
    def __init__(self, client: SmartMentorClient) -> None:
        self._client = client

    def active_enrollment(self, path_id: int) -> Enrollment | None:
        return active_enrollment(self._client.list_my_enrollments(), path_id)

    def enroll(self, path_id: int, profile_description: str) -> Enrollment:
        return self._client.enroll(path_id, profile_description)

    def diagnostic(self, enrollment_id: int) -> Diagnostic:
        return self._client.get_diagnostic(enrollment_id)

    def submit_diagnostic(self, enrollment_id: int, answers: Answers) -> Diagnostic:
        return self._client.submit_diagnostic(enrollment_id, answers)

    def confirm_objective(self, enrollment_id: int, objective: str) -> Enrollment:
        return self._client.confirm_objective(enrollment_id, objective)
