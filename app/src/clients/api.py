"""Cliente HTTP de la API real (`APP_DATA_SOURCE=api`).

- El token se lee en **cada llamada** con `token_provider`; el cliente nunca lo guarda.
- Los errores `application/problem+json` (RFC 9457) se convierten en `ApiError` con su `code`.
- Las operaciones que cuestan o entregan llevan `Idempotency-Key` (contrato, sección 1).
- Cada petición lleva un `X-Request-ID` nuevo (trazabilidad app → API → ai/).
- No aplica reglas de negocio: devuelve lo que responde la API.
"""

import logging
import uuid
from collections.abc import Callable, Sequence
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from clients.base import ApiError
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
from clients.ops_learner import LearnerApiOps
from clients.ops_staff import StaffApiOps

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=3.0)

TokenProvider = Callable[[], str]


def _problem(response: httpx.Response) -> ApiError:
    """Convierte una respuesta de error en `ApiError`, con o sin cuerpo RFC 9457."""
    request_id = response.headers.get("X-Request-ID")
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and "code" in body:
        extra = {
            key: body[key]
            for key in ("errors", "cycle", "missing", "attempts_used", "max_attempts", "job_id")
            if key in body
        }
        return ApiError(
            response.status_code,
            str(body["code"]),
            str(body.get("detail", "")),
            request_id=str(body.get("request_id") or request_id or "") or None,
            retryable=bool(body.get("retryable", False)),
            extra=extra,
        )
    return ApiError(
        response.status_code,
        f"HTTP_{response.status_code}",
        response.reason_phrase,
        request_id=request_id,
    )


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as error:
        raise ApiError(502, "INVALID_RESPONSE", "not JSON") from error


class ApiClient(LearnerApiOps, StaffApiOps):
    """Implementa `SmartMentorClient` sobre `httpx`."""

    def __init__(
        self,
        base_url: str,
        token_provider: TokenProvider,
        *,
        http: httpx.Client | None = None,
    ) -> None:
        self._token_provider = token_provider
        self._http = http or httpx.Client(base_url=base_url, timeout=DEFAULT_TIMEOUT)

    # --- Infraestructura ---

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._token_provider()}",
            "X-Request-ID": str(uuid.uuid4()),
            "Accept": "application/json",
        }
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        try:
            response = self._http.request(
                method, f"{API_PREFIX}{path}", json=json, params=params, headers=headers
            )
        except httpx.HTTPError as error:
            logger.warning("API sin conexión: %s %s (%s)", method, path, type(error).__name__)
            raise ApiError(503, "SERVICE_UNAVAILABLE", "API unreachable") from error
        if response.is_error:
            problem = _problem(response)
            logger.info(
                "API %s %s -> %s %s (request_id=%s)",
                method,
                path,
                problem.status,
                problem.code,
                problem.request_id,
            )
            raise problem
        return response

    def _multipart(
        self, path: str, files: dict[str, tuple[str, bytes, str]], idempotency_key: str
    ) -> httpx.Response:
        """POST `multipart/form-data` (carga del syllabus, D1b)."""
        headers = {
            "Authorization": f"Bearer {self._token_provider()}",
            "X-Request-ID": str(uuid.uuid4()),
            "Idempotency-Key": idempotency_key,
        }
        try:
            response = self._http.post(f"{API_PREFIX}{path}", files=files, headers=headers)
        except httpx.HTTPError as error:
            raise ApiError(503, "SERVICE_UNAVAILABLE", "API unreachable") from error
        if response.is_error:
            raise _problem(response)
        return response

    @staticmethod
    def _parse[M: BaseModel](model: type[M], data: Any) -> M:
        try:
            return model.model_validate(data)
        except ValidationError as error:
            logger.warning("Respuesta inválida para %s: %s", model.__name__, error.error_count())
            raise ApiError(502, "INVALID_RESPONSE", model.__name__) from error

    @classmethod
    def _model[M: BaseModel](cls, model: type[M], response: httpx.Response) -> M:
        return cls._parse(model, _json(response))

    @classmethod
    def _page[M: BaseModel](cls, model: type[M], response: httpx.Response) -> Page[M]:
        page_model: type[Page[M]] = Page[model]  # type: ignore[valid-type]
        return cls._parse(page_model, _json(response))

    # --- Usuario actual, consentimientos y perfil ---

    def get_me(self) -> Me:
        return self._model(Me, self._request("GET", "/me"))

    def get_profile(self) -> Profile:
        return self._model(Profile, self._request("GET", "/me/profile"))

    def update_profile(self, update: ProfileUpdate) -> Profile:
        body = update.model_dump(mode="json")
        return self._model(Profile, self._request("PUT", "/me/profile", json=body))

    def list_consents(self) -> list[Consent]:
        response = self._request("GET", "/me/consents")
        return [self._parse(Consent, item) for item in _json(response)]

    def grant_consent(self, consent_type: ConsentType, document_version: str) -> Consent:
        body = {"consent_type": consent_type, "document_version": document_version}
        return self._model(Consent, self._request("POST", "/me/consents", json=body))

    def revoke_consent(self, consent_type: ConsentType) -> Consent:
        path = f"/me/consents/{consent_type}/revoke"
        return self._model(Consent, self._request("PATCH", path))

    def create_data_subject_request(
        self, request_type: RequestType, comment: str
    ) -> DataSubjectRequest:
        body = {"request_type": request_type, "comment": comment}
        response = self._request("POST", "/me/data-subject-requests", json=body)
        return self._model(DataSubjectRequest, response)

    # --- Aprendiz: catálogo, inscripción y diagnóstico ---

    def list_learning_paths(self, *, limit: int = 20, offset: int = 0) -> Page[LearningPathCard]:
        response = self._request(
            "GET", "/learning-paths", params={"limit": limit, "offset": offset}
        )
        return self._page(LearningPathCard, response)

    def create_enrollment(self, learning_path_id: int) -> Enrollment:
        body = {"learning_path_id": learning_path_id}
        return self._model(Enrollment, self._request("POST", "/me/enrollments", json=body))

    def list_enrollments(self, *, limit: int = 20, offset: int = 0) -> Page[Enrollment]:
        response = self._request(
            "GET", "/me/enrollments", params={"limit": limit, "offset": offset}
        )
        return self._page(Enrollment, response)

    def get_enrollment(self, enrollment_id: int) -> Enrollment:
        return self._model(Enrollment, self._request("GET", f"/me/enrollments/{enrollment_id}"))

    def create_diagnostic(self, enrollment_id: int) -> Diagnostic:
        response = self._request("POST", f"/me/enrollments/{enrollment_id}/diagnostic")
        return self._model(Diagnostic, response)

    def get_diagnostic(self, enrollment_id: int) -> Diagnostic:
        response = self._request("GET", f"/me/enrollments/{enrollment_id}/diagnostic")
        return self._model(Diagnostic, response)

    def save_diagnostic_answers(self, enrollment_id: int, answers: Sequence[LearnerAnswer]) -> int:
        body = {"answers": [answer.model_dump(mode="json") for answer in answers]}
        response = self._request(
            "PUT", f"/me/enrollments/{enrollment_id}/diagnostic/answers", json=body
        )
        return int(_json(response)["saved"])

    def submit_diagnostic(self, enrollment_id: int, *, idempotency_key: str) -> JobAccepted:
        response = self._request(
            "POST",
            f"/me/enrollments/{enrollment_id}/diagnostic/submit",
            idempotency_key=idempotency_key,
        )
        return self._model(JobAccepted, response)

    def get_diagnostic_result(self, enrollment_id: int) -> DiagnosticResult:
        response = self._request("GET", f"/me/enrollments/{enrollment_id}/diagnostic/result")
        return self._model(DiagnosticResult, response)

    def set_objective(self, enrollment_id: int, objective: Objective) -> Enrollment:
        response = self._request(
            "PUT",
            f"/me/enrollments/{enrollment_id}/objective",
            json=objective.model_dump(mode="json"),
        )
        return self._model(Enrollment, response)

    # --- Aprendiz: ruta, tema, intentos y cierre ---

    def get_path(self, enrollment_id: int) -> PathDetail:
        response = self._request("GET", f"/me/enrollments/{enrollment_id}/path")
        return self._model(PathDetail, response)

    def get_step_content(self, enrollment_id: int, step_id: int) -> StepContent:
        response = self._request("GET", f"/me/enrollments/{enrollment_id}/steps/{step_id}/content")
        return self._model(StepContent, response)

    def create_attempt(
        self,
        enrollment_id: int,
        step_id: int,
        assessment_type: AssessmentType,
        *,
        idempotency_key: str,
    ) -> Attempt | JobAccepted:
        response = self._request(
            "POST",
            f"/me/enrollments/{enrollment_id}/steps/{step_id}/attempts",
            json={"assessment_type": assessment_type},
            idempotency_key=idempotency_key,
        )
        if response.status_code == 202:
            return self._model(JobAccepted, response)
        return self._model(Attempt, response)

    def get_attempt(self, attempt_id: int) -> Attempt:
        return self._model(Attempt, self._request("GET", f"/me/attempts/{attempt_id}"))

    def save_attempt_answers(self, attempt_id: int, answers: Sequence[LearnerAnswer]) -> int:
        body = {"answers": [answer.model_dump(mode="json") for answer in answers]}
        response = self._request("PUT", f"/me/attempts/{attempt_id}/answers", json=body)
        return int(_json(response)["saved"])

    def submit_attempt(
        self, attempt_id: int, *, idempotency_key: str
    ) -> AttemptResult | JobAccepted:
        response = self._request(
            "POST", f"/me/attempts/{attempt_id}/submit", idempotency_key=idempotency_key
        )
        if response.status_code == 202:
            return self._model(JobAccepted, response)
        return self._model(AttemptResult, response)

    def get_attempt_result(self, attempt_id: int) -> AttemptResult:
        response = self._request("GET", f"/me/attempts/{attempt_id}/result")
        return self._model(AttemptResult, response)

    def request_answer_review(self, attempt_answer_id: int, comment: str) -> int:
        response = self._request(
            "POST",
            f"/me/attempt-answers/{attempt_answer_id}/review-request",
            json={"comment": comment},
        )
        return int(_json(response)["alert_id"])

    def create_final_attempt(
        self, enrollment_id: int, *, idempotency_key: str
    ) -> Attempt | JobAccepted:
        response = self._request(
            "POST",
            f"/me/enrollments/{enrollment_id}/final-attempts",
            idempotency_key=idempotency_key,
        )
        if response.status_code == 202:  # reintento sin preguntas no vistas (B-011)
            return self._model(JobAccepted, response)
        return self._model(Attempt, response)

    def get_review_plan(self, enrollment_id: int) -> ReviewPlan:
        response = self._request("GET", f"/me/enrollments/{enrollment_id}/review-plan")
        return self._model(ReviewPlan, response)

    def list_badges(self) -> list[BadgeSummary]:
        response = self._request("GET", "/me/badges")
        return [self._parse(BadgeSummary, item) for item in _json(response)]

    def get_badge(self, enrollment_id: int) -> BadgeSummary:
        response = self._request("GET", f"/me/enrollments/{enrollment_id}/badge")
        return self._model(BadgeSummary, response)

    def send_video_feedback(
        self,
        *,
        video_candidate_id: int,
        enrollment_id: int,
        rating: VideoRating,
        comment: str | None,
        watched_fully: bool,
    ) -> None:
        self._request(
            "POST",
            "/me/video-feedback",
            json={
                "video_candidate_id": video_candidate_id,
                "enrollment_id": enrollment_id,
                "rating": rating,
                "comment": comment,
                "watched_fully": watched_fully,
            },
        )

    def submit_final_survey(
        self,
        enrollment_id: int,
        *,
        likert: dict[str, int],
        sus_items: Sequence[int],
        comment: str | None,
    ) -> float:
        response = self._request(
            "POST",
            f"/me/enrollments/{enrollment_id}/surveys/final",
            json={"likert": likert, "sus_items": list(sus_items), "comment": comment},
        )
        return float(_json(response)["sus_score"])

    # --- Trabajos de IA ---

    def get_job(self, job_id: str) -> Job:
        return self._model(Job, self._request("GET", f"/jobs/{job_id}"))
