"""Cliente de fixtures (`APP_DATA_SOURCE=fixtures`): responde con los JSON de `tests/fixtures/`.

No aplica reglas de negocio: devuelve documentos ya escritos y validados contra los modelos del
contrato (`docs/contracts/api-v2.md`). La única «memoria» es un eco del estado de la sesión de
demostración (el consentimiento aceptado, el perfil guardado, la inscripción creada) para que se
pueda navegar; no calcula niveles, umbrales ni intentos.

Los botones «(Demo del prototipo)» de Figma no existen: los estados se eligen con un *escenario*
(`SCENARIOS`) en el selector de rol (A1).
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from clients.base import ApiError
from clients.models import (
    AssessmentType,
    Attempt,
    AttemptResult,
    BadgeSummary,
    Consent,
    ConsentGrant,
    ConsentType,
    DataSubjectRequest,
    Diagnostic,
    DiagnosticResult,
    Enrollment,
    Job,
    JobAccepted,
    LearnerAnswer,
    LearningPathCard,
    LearningPathRef,
    Me,
    NextAction,
    Objective,
    Page,
    PathDetail,
    Profile,
    ProfileUpdate,
    RequestType,
    ReviewPlan,
    Role,
    StepContent,
    VideoRating,
)
from clients.ops_learner import (
    LEARNER_SCENARIOS,
    LEARNER_SCENARIOS_BY_KEY,
    LearnerFixtureOps,
    LearnerScript,
)
from clients.ops_staff import StaffFixturesOps

DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


@dataclass(frozen=True)
class Scenario:
    """Escenario de datos: reemplaza a los botones «Demo» de Figma."""

    key: str
    role: Role
    label: str
    description: str
    me: str
    profile: str
    consents: str
    enrollments: str


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "learner",
        "learner",
        "Aprendiz",
        "Laura Martínez entra al catálogo, sin ruta todavía.",
        "me_learner",
        "profile",
        "consents",
        "enrollments_empty",
    ),
    Scenario(
        "learner_in_path",
        "learner",
        "Aprendiz con ruta en curso",
        "Laura Martínez con «Fundamentos de Machine Learning» en curso.",
        "me_learner",
        "profile",
        "consents",
        "enrollments_in_path",
    ),
    Scenario(
        "learner_new",
        "learner",
        "Aprendiz nuevo (primer ingreso)",
        "Camilo Rojas entra por primera vez: debe aceptar las autorizaciones.",
        "me_learner_new",
        "profile_empty",
        "consents_empty",
        "enrollments_empty",
    ),
    Scenario(
        "instructor",
        "instructor",
        "Instructor",
        "Elena Ramírez, instructora y aprendiz (cambio de perfil, CU-35).",
        "me_instructor",
        "profile",
        "consents",
        "enrollments_empty",
    ),
    Scenario(
        "admin",
        "admin",
        "Administrador",
        "Administrador de ejemplo, con los tres perfiles.",
        "me_admin",
        "profile",
        "consents",
        "enrollments_empty",
    ),
)

SCENARIOS = (
    *SCENARIOS,
    *(
        Scenario(
            s.key,
            "learner",
            s.label,
            s.description,
            "me_learner",
            "profile",
            "consents",
            s.enrollments,
        )
        for s in LEARNER_SCENARIOS
    ),
)
SCENARIOS_BY_KEY = {scenario.key: scenario for scenario in SCENARIOS}


@cache
def _read(directory: Path, name: str) -> Any:
    path = directory / f"{name}.json"
    if not path.is_file():
        raise ApiError(404, "NOT_FOUND", f"fixture {name} not found")
    return json.loads(path.read_text(encoding="utf-8"))


class FixturesClient(LearnerFixtureOps, StaffFixturesOps):
    """Implementa `SmartMentorClient` con documentos fijos y un eco mínimo del estado."""

    def __init__(
        self,
        scenario_key: str = "learner",
        *,
        directory: Path | None = None,
        script: LearnerScript | None = None,
    ) -> None:
        self._dir = directory or DEFAULT_FIXTURES_DIR
        self.scenario = SCENARIOS_BY_KEY[scenario_key]
        spec = LEARNER_SCENARIOS_BY_KEY.get(scenario_key)
        self._script = script or (spec.script if spec else LearnerScript())
        self._me = self._load(self.scenario.me, Me)
        self._profile = self._load(self.scenario.profile, Profile)
        self._consents = [
            Consent.model_validate(item) for item in _read(self._dir, self.scenario.consents)
        ]
        self._enrollments = self._load(self.scenario.enrollments, Page[Enrollment]).items
        self._job_polls: dict[str, int] = {}

    def _load[M: BaseModel](self, name: str, model: type[M]) -> M:
        return model.model_validate(_read(self._dir, name))

    # --- Usuario actual, consentimientos y perfil ---

    def get_me(self) -> Me:
        return self._me.model_copy(deep=True)

    def get_profile(self) -> Profile:
        return self._profile.model_copy(deep=True)

    def update_profile(self, update: ProfileUpdate) -> Profile:
        self._profile = Profile(
            **update.model_dump(),
            resume_completed_at=self._profile.resume_completed_at,
        )
        completeness = self._me.profile_completeness
        completeness.description = bool(update.description)
        completeness.resume = update.education_level is not None
        completeness.percent = 50 * (int(completeness.description) + int(completeness.resume))
        if update.description:
            # Como la API (`PUT /me/profile`): con descripción, las inscripciones que esperaban el
            # perfil pasan al diagnóstico. Sin esto E2b volvía a E2 en el modo `fixtures`.
            for enrollment in self._enrollments:
                _ready_for_diagnostic(enrollment)
        return self.get_profile()

    def list_consents(self) -> list[Consent]:
        return [consent.model_copy(deep=True) for consent in self._consents]

    def grant_consent(self, consent_type: ConsentType, document_version: str) -> Consent:
        consent = Consent(
            consent_type=consent_type,
            granted=True,
            document_version=document_version,
            granted_at=datetime.now(UTC),
        )
        self._consents = [c for c in self._consents if c.consent_type != consent_type] + [consent]
        grant = ConsentGrant(
            granted=True, document_version=document_version, granted_at=consent.granted_at
        )
        if consent_type == "data_processing":
            self._me.consent_status.data_processing = grant
            self._me.requires_consent = False
            self._me.is_new_user = False
        else:
            self._me.consent_status.pilot_research = grant
        return consent

    def revoke_consent(self, consent_type: ConsentType) -> Consent:
        revoked = Consent(consent_type=consent_type, granted=False)
        self._consents = [c for c in self._consents if c.consent_type != consent_type]
        if consent_type == "data_processing":
            self._me.consent_status.data_processing = ConsentGrant(granted=False)
            self._me.requires_consent = True
        else:
            self._me.consent_status.pilot_research = ConsentGrant(granted=False)
        return revoked

    def create_data_subject_request(
        self, request_type: RequestType, comment: str
    ) -> DataSubjectRequest:
        del comment
        return DataSubjectRequest(id=1, request_type=request_type, status="pending")

    # --- Aprendiz: catálogo, inscripción y diagnóstico ---

    def list_learning_paths(self, *, limit: int = 20, offset: int = 0) -> Page[LearningPathCard]:
        page = self._load("learning_paths", Page[LearningPathCard])
        items = page.items[offset : offset + limit]
        return Page[LearningPathCard](items=items, total=page.total, limit=limit, offset=offset)

    def create_enrollment(self, learning_path_id: int) -> Enrollment:
        for enrollment in self._enrollments:
            if enrollment.learning_path.id == learning_path_id:
                raise ApiError(409, "ENROLLMENT_ALREADY_EXISTS", "already enrolled")
        card = next((c for c in self.list_learning_paths().items if c.id == learning_path_id), None)
        if card is None:
            raise ApiError(422, "LEARNING_PATH_NOT_PUBLISHED", "path is not published")
        created = self._load("enrollment_profiling", Enrollment)
        created.id = 100 + learning_path_id
        created.learning_path = LearningPathRef(
            id=card.id, name=card.name, group_label=card.group_label
        )
        if self._profile.description:
            _ready_for_diagnostic(created)  # la API inscribe en `diagnosing` si ya hay perfil
        self._enrollments.append(created)
        return created.model_copy(deep=True)

    def list_enrollments(self, *, limit: int = 20, offset: int = 0) -> Page[Enrollment]:
        self.check_online()
        items = [e.model_copy(deep=True) for e in self._enrollments[offset : offset + limit]]
        return Page[Enrollment](
            items=items, total=len(self._enrollments), limit=limit, offset=offset
        )

    def get_enrollment(self, enrollment_id: int) -> Enrollment:
        self.check_online()
        for enrollment in self._enrollments:
            if enrollment.id == enrollment_id:
                return enrollment.model_copy(deep=True)
        raise ApiError(404, "ENROLLMENT_NOT_FOUND", "enrollment not found")

    def create_diagnostic(self, enrollment_id: int) -> Diagnostic:
        del enrollment_id
        return self.doc("diagnostic", Diagnostic)

    def get_diagnostic(self, enrollment_id: int) -> Diagnostic:
        del enrollment_id
        return self.doc("diagnostic", Diagnostic)

    def save_diagnostic_answers(self, enrollment_id: int, answers: Sequence[LearnerAnswer]) -> int:
        del enrollment_id
        self.check_online()
        return len(answers)

    def submit_diagnostic(self, enrollment_id: int, *, idempotency_key: str) -> JobAccepted:
        del enrollment_id, idempotency_key
        return self.accepted("diagnostic_submit")

    def get_diagnostic_result(self, enrollment_id: int) -> DiagnosticResult:
        del enrollment_id
        return self.doc("diagnostic_result", DiagnosticResult)

    def set_objective(self, enrollment_id: int, objective: Objective) -> Enrollment:
        del enrollment_id, objective
        updated = self.doc("set_objective", Enrollment)
        self.echo_next_action(updated.next_action)
        return updated

    # --- Aprendiz: ruta, tema, intentos y cierre ---

    def get_path(self, enrollment_id: int) -> PathDetail:
        del enrollment_id
        return self.doc("path", PathDetail)

    def get_step_content(self, enrollment_id: int, step_id: int) -> StepContent:
        del enrollment_id, step_id
        return self.doc("step_content", StepContent)

    def create_attempt(
        self,
        enrollment_id: int,
        step_id: int,
        assessment_type: AssessmentType,
        *,
        idempotency_key: str,
    ) -> Attempt | JobAccepted:
        del enrollment_id, step_id, assessment_type, idempotency_key
        if "poll_url" in self.doc_raw("create_attempt"):
            return self.accepted("create_attempt")
        return self.doc("create_attempt", Attempt)

    def get_attempt(self, attempt_id: int) -> Attempt:
        del attempt_id
        return self.doc("attempt", Attempt)

    def save_attempt_answers(self, attempt_id: int, answers: Sequence[LearnerAnswer]) -> int:
        del attempt_id
        self.check_online()
        return len(answers)

    def submit_attempt(
        self, attempt_id: int, *, idempotency_key: str
    ) -> AttemptResult | JobAccepted:
        del attempt_id, idempotency_key
        if "poll_url" in self.doc_raw("submit_attempt"):
            return self.accepted("submit_attempt")
        return self.doc("submit_attempt", AttemptResult)

    def get_attempt_result(self, attempt_id: int) -> AttemptResult:
        del attempt_id
        return self.doc("attempt_result", AttemptResult)

    def request_answer_review(self, attempt_answer_id: int, comment: str) -> int:
        del attempt_answer_id, comment
        self.check_online()
        return 1

    def create_final_attempt(
        self, enrollment_id: int, *, idempotency_key: str
    ) -> Attempt | JobAccepted:
        del enrollment_id, idempotency_key
        if "poll_url" in self.doc_raw("final_attempt"):
            return self.accepted("final_attempt")
        return self.doc("final_attempt", Attempt)

    def get_review_plan(self, enrollment_id: int) -> ReviewPlan:
        del enrollment_id
        return self.doc("review_plan", ReviewPlan)

    def list_badges(self) -> list[BadgeSummary]:
        return [self.doc("badge", BadgeSummary)]

    def get_badge(self, enrollment_id: int) -> BadgeSummary:
        del enrollment_id
        return self.doc("badge", BadgeSummary)

    def send_video_feedback(
        self,
        *,
        video_candidate_id: int,
        enrollment_id: int,
        rating: VideoRating,
        comment: str | None,
        watched_fully: bool,
    ) -> None:
        del video_candidate_id, enrollment_id, rating, comment, watched_fully
        self.check_online()

    def submit_final_survey(
        self,
        enrollment_id: int,
        *,
        likert: dict[str, int],
        sus_items: Sequence[int],
        comment: str | None,
    ) -> float:
        del enrollment_id, likert, sus_items, comment
        self.check_online()
        return 85.0

    # --- Trabajos de IA ---

    def get_job(self, job_id: str) -> Job:
        """La primera consulta devuelve «en curso» y las siguientes el resultado del escenario."""
        return self.job_document(job_id)


def _ready_for_diagnostic(enrollment: Enrollment) -> None:
    """`enrolled` o `profiling` → `diagnosing`, con `start_diagnostic` (contrato, sección 3.2)."""
    if enrollment.status in ("enrolled", "profiling"):
        enrollment.status = "diagnosing"
        enrollment.next_action = NextAction(type="start_diagnostic", screen="E3")
