"""Contrato del acceso a datos de la interfaz.

`SmartMentorClient` lista las operaciones de la API (`docs/contracts/api-v2.md`) que usa la
interfaz.
Lo implementan el cliente HTTP real (`api.py`) y el de fixtures (`fixtures.py`). Los servicios y las
páginas solo dependen de este Protocol: cambiar de fuente no los toca.

Un agente que agregue pantallas del instructor o del administrador agrega aquí sus operaciones
(una por ruta del contrato), en la sección de su rol.
"""

from collections.abc import Sequence
from typing import Any, Protocol

from clients.models import (
    AssessmentType,
    Attempt,
    AttemptResult,
    BadgeSummary,
    Consent,
    ConsentType,
    DataSubjectRequest,
    Diagnostic,
    DiagnosticResult,
    Enrollment,
    Job,
    JobAccepted,
    LearnerAnswer,
    LearningPathCard,
    Me,
    Objective,
    Page,
    PathDetail,
    Profile,
    ProfileUpdate,
    RequestType,
    ReviewPlan,
    StepContent,
    VideoRating,
)
from clients.models_learner import LearnerOps
from clients.ops_staff_contract import StaffOps


class ApiError(Exception):
    """Error de la API (RFC 9457): `status`, `code` estable y, si existen, sus extensiones.

    Sin conexión o con tiempo agotado el cliente lanza `ApiError(503, "SERVICE_UNAVAILABLE")`;
    la interfaz nunca muestra el detalle técnico, solo el `request_id` va al registro.
    """

    def __init__(
        self,
        status: int,
        code: str,
        detail: str = "",
        *,
        request_id: str | None = None,
        retryable: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"{status} {code}: {detail}")
        self.status = status
        self.code = code
        self.detail = detail
        self.request_id = request_id
        self.retryable = retryable
        self.extra: dict[str, Any] = extra or {}


class SmartMentorClient(LearnerOps, StaffOps, Protocol):
    """Operaciones que la interfaz pide a la API. El token lo pone cada implementación."""

    # --- Usuario actual, consentimientos y perfil (sección 2) ---
    def get_me(self) -> Me: ...
    def get_profile(self) -> Profile: ...
    def update_profile(self, update: ProfileUpdate) -> Profile: ...
    def list_consents(self) -> list[Consent]: ...
    def grant_consent(self, consent_type: ConsentType, document_version: str) -> Consent: ...
    def revoke_consent(self, consent_type: ConsentType) -> Consent: ...
    def create_data_subject_request(
        self, request_type: RequestType, comment: str
    ) -> DataSubjectRequest: ...

    # --- Aprendiz: catálogo, inscripción y diagnóstico (secciones 3 y 4) ---
    def list_learning_paths(
        self, *, limit: int = 20, offset: int = 0
    ) -> Page[LearningPathCard]: ...
    def create_enrollment(self, learning_path_id: int) -> Enrollment: ...
    def list_enrollments(self, *, limit: int = 20, offset: int = 0) -> Page[Enrollment]: ...
    def get_enrollment(self, enrollment_id: int) -> Enrollment: ...
    def create_diagnostic(self, enrollment_id: int) -> Diagnostic: ...
    def get_diagnostic(self, enrollment_id: int) -> Diagnostic: ...
    def save_diagnostic_answers(
        self, enrollment_id: int, answers: Sequence[LearnerAnswer]
    ) -> int: ...
    def submit_diagnostic(self, enrollment_id: int, *, idempotency_key: str) -> JobAccepted: ...
    def get_diagnostic_result(self, enrollment_id: int) -> DiagnosticResult: ...
    def set_objective(self, enrollment_id: int, objective: Objective) -> Enrollment: ...

    # --- Aprendiz: ruta, tema, intentos y cierre ---
    def get_path(self, enrollment_id: int) -> PathDetail: ...
    def get_step_content(self, enrollment_id: int, step_id: int) -> StepContent: ...
    def create_attempt(
        self,
        enrollment_id: int,
        step_id: int,
        assessment_type: AssessmentType,
        *,
        idempotency_key: str,
    ) -> Attempt | JobAccepted: ...
    def get_attempt(self, attempt_id: int) -> Attempt: ...
    def save_attempt_answers(self, attempt_id: int, answers: Sequence[LearnerAnswer]) -> int: ...
    def submit_attempt(
        self, attempt_id: int, *, idempotency_key: str
    ) -> AttemptResult | JobAccepted: ...
    def get_attempt_result(self, attempt_id: int) -> AttemptResult: ...
    def request_answer_review(self, attempt_answer_id: int, comment: str) -> int: ...
    def create_final_attempt(self, enrollment_id: int, *, idempotency_key: str) -> Attempt: ...
    def get_review_plan(self, enrollment_id: int) -> ReviewPlan: ...
    def list_badges(self) -> list[BadgeSummary]: ...
    def get_badge(self, enrollment_id: int) -> BadgeSummary: ...
    def send_video_feedback(
        self,
        *,
        video_candidate_id: int,
        enrollment_id: int,
        rating: VideoRating,
        comment: str | None,
        watched_fully: bool,
    ) -> None: ...
    def submit_final_survey(
        self,
        enrollment_id: int,
        *,
        likert: dict[str, int],
        sus_items: Sequence[int],
        comment: str | None,
    ) -> float: ...

    # --- Trabajos de IA (sección 7) ---
    def get_job(self, job_id: str) -> Job: ...
