"""Operaciones de la API para el instructor y el administrador (`api-v2.md`, secciones 5 y 6).

Viven en un archivo propio para no chocar con las del aprendiz. Se enchufan con una línea en cada
cliente: `SmartMentorClient` hereda `StaffOps`, `ApiClient` hereda `StaffApiOps` y
`FixturesClient` hereda `StaffFixturesOps`.

El cliente de fixtures lee `tests/fixtures/staff/<nombre>.json`; un *escenario* (`staff_scenario`)
reemplaza el documento por `<nombre>__<escenario>.json` si existe. `forbidden` responde 403 y
`error` responde 503 en todas las operaciones. No aplica reglas de negocio.
"""

import json
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from clients.admin_adapter import (
    admin_enrollment_from_api,
    admin_enrollments_page_from_api,
    admin_user_from_api,
    llm_logs_page_from_api,
    llm_summary_from_api,
    metrics_from_api,
)
from clients.base import ApiError
from clients.content_adapter import item_from_api, item_patch_for_api, resource_from_api
from clients.dashboard_adapter import dashboard_from_api, is_api_dashboard
from clients.evaluation_adapter import (
    annotation_queue_from_api,
    grading_queue_from_api,
    grading_result_from_api,
    topic_videos_from_api,
    video_from_api,
    video_quality_from_api,
)
from clients.learner_detail_adapter import is_api_learner_detail, learner_detail_from_api
from clients.models import ROLES, Job, JobAccepted, Page, Role
from clients.models_staff import (
    AdminEnrollment,
    AdminUser,
    AnnotationBody,
    AnnotationQueue,
    AttemptGrant,
    Course,
    CourseCreate,
    CourseEvaluator,
    CourseMaterial,
    CourseTopic,
    CourseTopics,
    Dashboard,
    ExtractionMetrics,
    GradingQueue,
    HumanGradingBody,
    HumanGradingResult,
    ItemPatch,
    LearnerDetail,
    LlmCallLog,
    LlmSummary,
    MaterialOrigin,
    MetricsEvaluation,
    Resource,
    ReviewItem,
    SampleType,
    TopicGraphDoc,
    TopicVideos,
    TopicWrite,
    UserCreate,
    VideoCandidate,
    VideoQuality,
    VideoStatus,
)
from clients.models_staff import PathSettings as PathSettingsModel
from clients.ops_staff_contract import StaffOps

__all__ = ["StaffApiOps", "StaffFixturesOps", "StaffOps"]

STAFF_SCENARIOS = ("default", "empty", "forbidden", "error", "loading", "no_text", "failed")


# --- Cliente HTTP -----------------------------------------------------------------------------


_MAX_PAGE = 100
"""Tope de `limit` de los listados de la API."""


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as error:
        raise ApiError(502, "INVALID_RESPONSE", "not JSON") from error


def _parse[M: BaseModel](model: type[M], data: Any) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as error:
        raise ApiError(502, "INVALID_RESPONSE", model.__name__) from error


def _material_content_type(file_name: str) -> str:
    """Tipo del apunte para el multipart; la API decide por la extensión (PDF, TXT o MD)."""
    lower = file_name.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith((".md", ".markdown")):
        return "text/markdown"
    return "text/plain"


def _page[M: BaseModel](model: type[M], data: Any) -> Page[M]:
    page_model: type[Page[M]] = Page[model]  # type: ignore[valid-type]
    return _parse(page_model, data)


class StaffApiOps:
    """Implementación HTTP. `ApiClient` sobrescribe `_request` con la suya."""

    _upload_timeout: httpx.Timeout
    """Tiempo de espera de las cargas de archivos; lo fija `ApiClient`."""

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> httpx.Response:
        raise NotImplementedError

    def _multipart(
        self,
        path: str,
        files: dict[str, tuple[str, bytes, str]],
        idempotency_key: str | None,
        data: dict[str, str] | None = None,
    ) -> httpx.Response:
        raise NotImplementedError

    def _get[M: BaseModel](self, model: type[M], path: str, **params: Any) -> M:
        response = self._request("GET", path, params=params or None)
        return _parse(model, _json(response))

    def _send[M: BaseModel](
        self,
        model: type[M],
        method: str,
        path: str,
        body: Any = None,
        *,
        key: str | None = None,
    ) -> M:
        response = self._request(method, path, json=body, idempotency_key=key)
        return _parse(model, _json(response))

    # Instructor: cursos, temas y grafo

    def list_courses(
        self, *, mine: bool = True, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> Page[Course]:
        params: dict[str, Any] = {"mine": str(mine).lower(), "limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return _page(Course, _json(self._request("GET", "/courses", params=params)))

    def create_course(self, body: CourseCreate) -> Course:
        payload = {
            "name": body.name,
            "description": body.description,
            "learning_path": {"name": body.learning_path_name, "group_label": body.group_label},
        }
        return self._send(Course, "POST", "/courses", payload)

    def get_course(self, course_id: int) -> Course:
        return self._get(Course, f"/courses/{course_id}")

    def upload_syllabus(
        self,
        course_id: int,
        *,
        text: str | None,
        file: tuple[str, bytes] | None,
        idempotency_key: str,
    ) -> JobAccepted:
        path = f"/courses/{course_id}/syllabus"
        if file is not None:
            name, content = file
            response = self._multipart(
                path, {"file": (name, content, "application/pdf")}, idempotency_key
            )
        else:
            # El texto pegado llega al mismo endpoint que el PDF: misma espera larga (B-055).
            response = self._request(
                "POST",
                path,
                json={"text": text},
                idempotency_key=idempotency_key,
                timeout=self._upload_timeout,
            )
        return _parse(JobAccepted, _json(response))

    def start_extraction(
        self, course_id: int, *, confirm_discard_review: bool, idempotency_key: str
    ) -> JobAccepted:
        body = {"confirm_discard_review": confirm_discard_review}
        return self._send(
            JobAccepted, "POST", f"/courses/{course_id}/extractions", body, key=idempotency_key
        )

    def upload_material(
        self, course_id: int, *, file: tuple[str, bytes], origin: MaterialOrigin
    ) -> CourseMaterial:
        """Sube un apunte; la API no duplica el mismo archivo (responde el que ya existía)."""
        name, content = file
        response = self._multipart(
            f"/courses/{course_id}/materials",
            {"file": (name, content, _material_content_type(name))},
            None,
            data={"origin": origin},
        )
        return _parse(CourseMaterial, _json(response))

    def list_materials(self, course_id: int) -> list[CourseMaterial]:
        data = _json(self._request("GET", f"/courses/{course_id}/materials"))
        if not isinstance(data, list):
            raise ApiError(502, "INVALID_RESPONSE", "CourseMaterial list")
        return [_parse(CourseMaterial, item) for item in data]

    def deactivate_material(self, course_id: int, material_id: int) -> CourseMaterial:
        """Quita el apunte del RAG (R-010); la API lo desactiva, no lo borra."""
        path = f"/courses/{course_id}/materials/{material_id}/deactivate"
        return self._send(CourseMaterial, "PATCH", path)

    def poll_job(self, job_id: str) -> Job:
        return self._get(Job, f"/jobs/{job_id}")

    def list_course_topics(self, course_id: int) -> CourseTopics:
        return self._get(CourseTopics, f"/courses/{course_id}/topics")

    def get_topic_graph(self, course_id: int) -> TopicGraphDoc:
        return self._get(TopicGraphDoc, f"/courses/{course_id}/topic-graph")

    def create_topic(self, course_id: int, body: TopicWrite) -> CourseTopic:
        payload = body.model_dump(mode="json")
        return self._send(CourseTopic, "POST", f"/courses/{course_id}/topics", payload)

    def update_topic(self, topic_id: int, body: TopicWrite) -> CourseTopic:
        return self._send(CourseTopic, "PUT", f"/topics/{topic_id}", body.model_dump(mode="json"))

    def deactivate_topic(self, topic_id: int) -> CourseTopic:
        return self._send(CourseTopic, "PATCH", f"/topics/{topic_id}/deactivate")

    def publish_course(self, course_id: int, *, idempotency_key: str) -> JobAccepted:
        return self._send(JobAccepted, "POST", f"/courses/{course_id}/publish", key=idempotency_key)

    def get_extraction_metrics(self, course_id: int) -> ExtractionMetrics:
        return self._get(ExtractionMetrics, f"/courses/{course_id}/extraction-metrics")

    def set_course_owner(self, course_id: int, owner_user_id: int | None) -> Course:
        body = {"owner_user_id": owner_user_id}
        return self._send(Course, "PATCH", f"/courses/{course_id}/owner", body)

    def archive_course(self, course_id: int) -> Course:
        return self._send(Course, "POST", f"/courses/{course_id}/archive")

    # Instructor: ruta, avance y aprendices

    def get_dashboard(self, path_id: int) -> Dashboard:
        data = _json(self._request("GET", f"/learning-paths/{path_id}/dashboard"))
        if is_api_dashboard(data):
            data = dashboard_from_api(data)
        return _parse(Dashboard, data)

    def update_path_settings(self, path_id: int, body: PathSettingsModel) -> PathSettingsModel:
        return self._send(
            PathSettingsModel,
            "PATCH",
            f"/learning-paths/{path_id}/settings",
            body.model_dump(mode="json"),
        )

    def get_learner_detail(self, path_id: int, enrollment_id: int) -> LearnerDetail:
        url = f"/learning-paths/{path_id}/learners/{enrollment_id}"
        data = _json(self._request("GET", url))
        if is_api_learner_detail(data):
            data = learner_detail_from_api(data, path_id)
        return _parse(LearnerDetail, data)

    def grant_step_attempts(self, step_id: int, attempts: int, note: str | None) -> AttemptGrant:
        body = {"attempts": attempts, "note": note}
        return self._send(AttemptGrant, "POST", f"/path-steps/{step_id}/attempt-grants", body)

    def grant_final_attempts(
        self, enrollment_id: int, attempts: int, note: str | None
    ) -> AttemptGrant:
        body = {"attempts": attempts, "note": note}
        path = f"/enrollments/{enrollment_id}/final-attempt-grants"
        return self._send(AttemptGrant, "POST", path, body)

    # Instructor: contenido, videos y evaluación

    def list_topic_resources(self, topic_id: int) -> list[Resource]:
        data = _json(self._request("GET", f"/topics/{topic_id}/resources"))
        return [_parse(Resource, resource_from_api(item)) for item in data]

    def review_resource(self, resource_id: int, review_status: str) -> Resource:
        body = {"review_status": review_status}
        response = self._request("PATCH", f"/resources/{resource_id}/review", json=body)
        return _parse(Resource, resource_from_api(_json(response)))

    def update_resource_content(self, resource_id: int, content: dict[str, Any]) -> Resource:
        response = self._request("PUT", f"/resources/{resource_id}/content", json=content)
        return _parse(Resource, resource_from_api(_json(response)))

    def regenerate_resource(self, resource_id: int, *, idempotency_key: str) -> JobAccepted:
        return self._send(
            JobAccepted, "POST", f"/resources/{resource_id}/regenerate", key=idempotency_key
        )

    def list_topic_items(self, topic_id: int) -> Page[ReviewItem]:
        response = self._request("GET", f"/topics/{topic_id}/items", params={"limit": 100})
        page = _json(response)
        if isinstance(page, dict):
            page = {**page, "items": [item_from_api(i) for i in page.get("items") or []]}
        return _page(ReviewItem, page)

    def update_item(self, item_id: int, patch: ItemPatch) -> ReviewItem:
        body = item_patch_for_api(patch.model_dump(mode="json", exclude_none=True))
        response = self._request("PATCH", f"/items/{item_id}", json=body)
        return _parse(ReviewItem, item_from_api(_json(response)))

    def list_video_candidates(self, topic_id: int) -> TopicVideos:
        data = _json(self._request("GET", f"/topics/{topic_id}/video-candidates"))
        return _parse(TopicVideos, topic_videos_from_api(data))

    def search_video_candidates(self, topic_id: int, *, idempotency_key: str) -> JobAccepted:
        """Vuelve a buscar los videos del tema en YouTube (B-064)."""
        return self._send(
            JobAccepted,
            "POST",
            f"/topics/{topic_id}/video-candidates/search",
            key=idempotency_key,
        )

    def update_video_candidate(
        self, candidate_id: int, *, status: VideoStatus | None, is_relevant: bool | None
    ) -> VideoCandidate:
        body = {
            k: v for k, v in {"status": status, "is_relevant": is_relevant}.items() if v is not None
        }
        response = self._request("PATCH", f"/video-candidates/{candidate_id}", json=body)
        return _parse(VideoCandidate, video_from_api(_json(response)))

    def add_video_candidate(
        self, topic_id: int, youtube_video_id: str, title: str
    ) -> VideoCandidate:
        body = {"youtube_video_id": youtube_video_id, "title": title}
        response = self._request("POST", f"/topics/{topic_id}/video-candidates", json=body)
        return _parse(VideoCandidate, video_from_api(_json(response)))

    def get_video_quality(self, path_id: int) -> VideoQuality:
        response = self._request("GET", f"/learning-paths/{path_id}/video-quality")
        return _parse(VideoQuality, video_quality_from_api(_json(response)))

    def get_annotation_queue(self, course_id: int) -> AnnotationQueue:
        params = {"course_id": course_id}
        response = self._request("GET", "/evaluation/annotation-queue", params=params)
        return _parse(AnnotationQueue, annotation_queue_from_api(_json(response)))

    def annotate_item(self, item_id: int, body: AnnotationBody) -> None:
        self._request("POST", f"/items/{item_id}/annotations", json=body.model_dump(mode="json"))

    def get_grading_queue(self, sample: SampleType) -> GradingQueue:
        response = self._request("GET", "/evaluation/grading-queue", params={"sample": sample})
        return _parse(GradingQueue, grading_queue_from_api(_json(response), sample))

    def grade_answer(self, attempt_answer_id: int, body: HumanGradingBody) -> HumanGradingResult:
        path = f"/attempt-answers/{attempt_answer_id}/human-gradings"
        response = self._request("POST", path, json=body.model_dump(mode="json"))
        return _parse(HumanGradingResult, grading_result_from_api(_json(response)))

    # Administrador

    # AD1. La API publica los usuarios con el CRUD genérico (`/users`, sin roles y solo activos
    # por defecto) y los roles aparte (`/roles`, `/user-roles`, `/users/{id}/roles`). La pantalla
    # quiere cada usuario con sus roles, activos e inactivos: se arma aquí sin cambiar la API.

    def _users(self, *, active: bool, limit: int, offset: int) -> tuple[list[Any], int]:
        params = {"active": active, "limit": limit, "offset": offset}
        data = _json(self._request("GET", "/users", params=params))
        return list(data.get("items") or []), int(data.get("total", 0))

    def _all_pages(self, path: str, **params: Any) -> list[Any]:
        items: list[Any] = []
        while True:
            query = {**params, "limit": _MAX_PAGE, "offset": len(items)}
            data = _json(self._request("GET", path, params=query))
            batch = list(data.get("items") or [])
            items.extend(batch)
            if not batch or len(items) >= int(data.get("total", 0)):
                return items

    def _roles_by_user(self) -> dict[int, list[Role]]:
        # Solo los roles que la interfaz conoce; otro código de la base no se muestra.
        codes: dict[int, Role] = {
            int(r["id"]): r["code"] for r in self._all_pages("/roles") if r.get("code") in ROLES
        }
        roles: dict[int, list[Role]] = {}
        for link in self._all_pages("/user-roles"):
            code = codes.get(int(link["role_id"]))
            if code is not None:
                roles.setdefault(int(link["user_id"]), []).append(code)
        return {user_id: sorted(found, key=ROLES.index) for user_id, found in roles.items()}

    def _user_roles(self, user_id: int) -> list[Role]:
        data = _json(self._request("GET", f"/users/{user_id}/roles"))
        return [code for code in data.get("roles") or [] if code in ROLES]

    def list_users(self, *, limit: int = 100, offset: int = 0) -> Page[AdminUser]:
        active, active_total = self._users(active=True, limit=limit, offset=offset)
        inactive: list[Any] = []
        inactive_total = 0
        if len(active) < limit:
            # Los inactivos van después de los activos, para poder reactivarlos.
            start = max(0, offset - active_total)
            inactive, inactive_total = self._users(
                active=False, limit=limit - len(active), offset=start
            )
        else:
            _, inactive_total = self._users(active=False, limit=1, offset=0)
        roles = self._roles_by_user()
        items = [
            admin_user_from_api(user, roles.get(int(user["id"]), []))
            for user in [*active, *inactive]
        ]
        return _page(
            AdminUser,
            {
                "items": items,
                "total": active_total + inactive_total,
                "limit": limit,
                "offset": offset,
            },
        )

    def create_user(self, body: UserCreate) -> AdminUser:
        user = _json(
            self._request("POST", "/users", json={"email": body.email, "full_name": body.full_name})
        )
        roles = self.set_user_roles(int(user["id"]), body.roles) if body.roles else []
        return _parse(AdminUser, admin_user_from_api(user, roles))

    def set_user_roles(self, user_id: int, roles: Sequence[Role]) -> list[Role]:
        response = self._request("PUT", f"/users/{user_id}/roles", json={"roles": list(roles)})
        roles_out: list[Role] = list(_json(response)["roles"])
        return roles_out

    def set_user_active(self, user_id: int, active: bool) -> AdminUser:
        action = "activate" if active else "deactivate"
        user = _json(self._request("PATCH", f"/users/{user_id}/{action}"))
        return _parse(AdminUser, admin_user_from_api(user, self._user_roles(user_id)))

    def get_llm_summary(self) -> LlmSummary:
        response = self._request("GET", "/llm-call-logs/summary")
        return _parse(LlmSummary, llm_summary_from_api(_json(response)))

    def list_llm_logs(self, *, limit: int = 50, offset: int = 0) -> Page[LlmCallLog]:
        response = self._request("GET", "/llm-call-logs", params={"limit": limit, "offset": offset})
        return _page(LlmCallLog, llm_logs_page_from_api(_json(response)))

    def get_evaluation_metrics(self, learning_path_id: int | None = None) -> MetricsEvaluation:
        params = None if learning_path_id is None else {"learning_path_id": learning_path_id}
        response = self._request("GET", "/metrics/evaluation", params=params)
        return _parse(MetricsEvaluation, metrics_from_api(_json(response)))

    # AD5 · Evaluadores de un curso (B-036). La API los asigna y los quita (solo administrador).

    def list_course_evaluators(self, course_id: int) -> list[CourseEvaluator]:
        data = _json(self._request("GET", f"/courses/{course_id}/evaluators"))
        return [_parse(CourseEvaluator, item) for item in data or []]

    def assign_course_evaluator(self, course_id: int, user_id: int) -> CourseEvaluator:
        body = {"user_id": user_id}
        return self._send(CourseEvaluator, "POST", f"/courses/{course_id}/evaluators", body)

    def remove_course_evaluator(self, evaluator_id: int) -> CourseEvaluator:
        path = f"/course-evaluators/{evaluator_id}/deactivate"
        return self._send(CourseEvaluator, "PATCH", path)

    def list_admin_enrollments(self, *, limit: int = 100, offset: int = 0) -> Page[AdminEnrollment]:
        response = self._request("GET", "/enrollments", params={"limit": limit, "offset": offset})
        return _page(AdminEnrollment, admin_enrollments_page_from_api(_json(response)))

    def _enrollment(self, method: str, path: str, body: dict[str, Any]) -> AdminEnrollment:
        response = self._request(method, path, json=body)
        return _parse(AdminEnrollment, admin_enrollment_from_api(_json(response)))

    def create_admin_enrollment(self, user_id: int, learning_path_id: int) -> AdminEnrollment:
        body = {"user_id": user_id, "learning_path_id": learning_path_id}
        return self._enrollment("POST", "/enrollments", body)

    def withdraw_enrollment(self, enrollment_id: int, note: str) -> AdminEnrollment:
        path = f"/enrollments/{enrollment_id}/withdraw"
        return self._enrollment("PATCH", path, {"note": note})

    def move_enrollment(self, enrollment_id: int, learning_path_id: int) -> AdminEnrollment:
        body = {"learning_path_id": learning_path_id}
        return self._enrollment("PATCH", f"/enrollments/{enrollment_id}/move", body)


# --- Cliente de fixtures ----------------------------------------------------------------------


@cache
def _read_doc(directory: Path, name: str) -> Any:
    path = directory / "staff" / f"{name}.json"
    if not path.is_file():
        raise ApiError(404, "NOT_FOUND", f"fixture staff/{name} not found")
    return json.loads(path.read_text(encoding="utf-8"))


class StaffFixturesOps:
    """Responde con `tests/fixtures/staff/*.json`; el escenario cambia el documento."""

    _dir: Path
    staff_scenario: str = "default"
    _staff_polls: dict[str, int]

    def _doc(self, name: str, *fallbacks: str) -> Any:
        scenario = self.staff_scenario
        if scenario == "forbidden":
            raise ApiError(403, "INSUFFICIENT_ROLE", "role required")
        if scenario == "error":
            raise ApiError(503, "SERVICE_UNAVAILABLE", "API unreachable")
        for candidate in (name, *fallbacks):
            for variant in (f"{candidate}__{scenario}", candidate):
                if (self._dir / "staff" / f"{variant}.json").is_file():
                    return _read_doc(self._dir, variant)
        raise ApiError(404, "NOT_FOUND", f"fixture staff/{name} not found")

    def _model[M: BaseModel](self, model: type[M], name: str, *fallbacks: str) -> M:
        return model.model_validate(self._doc(name, *fallbacks))

    def _list[M: BaseModel](self, model: type[M], name: str) -> list[M]:
        return [model.model_validate(item) for item in self._doc(name)]

    # Instructor: cursos, temas y grafo

    def list_courses(
        self, *, mine: bool = True, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> Page[Course]:
        page = self._model(Page[Course], "courses" if mine else "admin_courses")
        archived = self._archived_course_ids()
        for course in page.items:
            if course.id in archived:
                course.status = "archived"
        everything = [c for c in page.items if status is None or c.status == status]
        items = everything[offset : offset + limit]
        return Page[Course](items=items, total=len(everything), limit=limit, offset=offset)

    def _archived_course_ids(self) -> set[int]:
        """Eco mínimo de «Archivar»: los cursos archivados en esta sesión de fixtures."""
        if not hasattr(self, "_archived"):
            self._archived: set[int] = set()
        return self._archived

    def create_course(self, body: CourseCreate) -> Course:
        course = self._model(Course, "course_new")
        course.name = body.name
        course.description = body.description
        return course

    def get_course(self, course_id: int) -> Course:
        return self._model(Course, f"course_{course_id}", "course")

    def upload_syllabus(
        self,
        course_id: int,
        *,
        text: str | None,
        file: tuple[str, bytes] | None,
        idempotency_key: str,
    ) -> JobAccepted:
        del course_id, text, file, idempotency_key
        if self.staff_scenario == "no_text":
            raise ApiError(422, "SYLLABUS_NO_TEXT", "no selectable text")
        return self._model(JobAccepted, "job_accepted")

    def start_extraction(
        self, course_id: int, *, confirm_discard_review: bool, idempotency_key: str
    ) -> JobAccepted:
        del course_id, confirm_discard_review, idempotency_key
        return self._model(JobAccepted, "job_accepted")

    def _materials(self) -> list[CourseMaterial]:
        """Eco mínimo de los apuntes: los de `staff/materials.json` más los subidos en la sesión."""
        if not hasattr(self, "_uploaded_materials"):
            self._uploaded_materials: list[CourseMaterial] = self._list(CourseMaterial, "materials")
        return self._uploaded_materials

    def upload_material(
        self, course_id: int, *, file: tuple[str, bytes], origin: MaterialOrigin
    ) -> CourseMaterial:
        name, content = file
        if self.staff_scenario == "no_text":
            raise ApiError(422, "MATERIAL_NO_TEXT", "no selectable text")
        material = self._model(CourseMaterial, "material")
        material.id = max((m.id for m in self._materials()), default=0) + 1
        material.course_id = course_id
        material.file_name = name
        material.origin = origin
        material.byte_size = len(content)
        material.source_type = "pdf" if name.lower().endswith(".pdf") else "text"
        self._materials().append(material)
        return material

    def list_materials(self, course_id: int) -> list[CourseMaterial]:
        return [m for m in self._materials() if m.course_id == course_id and m.active]

    def deactivate_material(self, course_id: int, material_id: int) -> CourseMaterial:
        found = next(
            (m for m in self._materials() if m.id == material_id and m.course_id == course_id),
            None,
        )
        if found is None:
            raise ApiError(404, "MATERIAL_NOT_FOUND", "material not found")
        found.active = False
        return found

    def poll_job(self, job_id: str) -> Job:
        """«loading»: siempre en curso; «failed»: falla; si no, en curso la primera vez."""
        polls = getattr(self, "_staff_polls", {})
        self._staff_polls = polls
        count = polls.get(job_id, 0)
        polls[job_id] = count + 1
        if self.staff_scenario == "loading":
            name = "job_running"
        elif self.staff_scenario == "failed":
            name = "job_failed"
        else:
            name = "job_running" if count == 0 else "job_succeeded"
        job = Job.model_validate(_read_doc(self._dir, name))
        job.job_id = job_id
        return job

    def list_course_topics(self, course_id: int) -> CourseTopics:
        return self._model(CourseTopics, f"topics_{course_id}", "topics")

    def get_topic_graph(self, course_id: int) -> TopicGraphDoc:
        return self._model(TopicGraphDoc, f"topic_graph_{course_id}", "topic_graph")

    def create_topic(self, course_id: int, body: TopicWrite) -> CourseTopic:
        del course_id
        data = dict(self._doc("topic"))
        data.update(body.model_dump(mode="json"))
        data["review_status"] = "added"
        data["origin"] = "instructor"
        return CourseTopic.model_validate(data)

    def update_topic(self, topic_id: int, body: TopicWrite) -> CourseTopic:
        data = dict(self._doc("topic"))
        data.update(body.model_dump(mode="json"))
        data["id"] = topic_id
        data["review_status"] = "corrected"
        return CourseTopic.model_validate(data)

    def deactivate_topic(self, topic_id: int) -> CourseTopic:
        data = dict(self._doc("topic"))
        data["id"] = topic_id
        data["review_status"] = "deleted"
        return CourseTopic.model_validate(data)

    def publish_course(self, course_id: int, *, idempotency_key: str) -> JobAccepted:
        del course_id, idempotency_key
        return self._model(JobAccepted, "job_accepted")

    def get_extraction_metrics(self, course_id: int) -> ExtractionMetrics:
        del course_id
        return self._model(ExtractionMetrics, "extraction_metrics")

    def set_course_owner(self, course_id: int, owner_user_id: int | None) -> Course:
        del owner_user_id
        return self.get_course(course_id)

    def archive_course(self, course_id: int) -> Course:
        course = next(
            (c for c in self.list_courses(mine=True).items if c.id == course_id),
            None,
        ) or self.get_course(course_id)
        if course.status not in ("draft", "published", "archived"):
            raise ApiError(
                409,
                "INVALID_STATE_TRANSITION",
                f"Only a draft or published course can be archived (it is {course.status}).",
            )
        self._archived_course_ids().add(course_id)
        course.status = "archived"
        return course

    # Instructor: ruta, avance y aprendices

    def get_dashboard(self, path_id: int) -> Dashboard:
        del path_id
        return self._model(Dashboard, "dashboard")

    def update_path_settings(self, path_id: int, body: PathSettingsModel) -> PathSettingsModel:
        del path_id
        if self.staff_scenario == "pilot_running" and not body.confirm_pilot_change:
            raise ApiError(409, "PILOT_RUNNING", "pilot is running")
        return body

    def get_learner_detail(self, path_id: int, enrollment_id: int) -> LearnerDetail:
        del path_id
        return self._model(LearnerDetail, f"learner_detail_{enrollment_id}", "learner_detail")

    def grant_step_attempts(self, step_id: int, attempts: int, note: str | None) -> AttemptGrant:
        del step_id
        data = self._doc("attempt_grant")
        return AttemptGrant.model_validate({**data, "attempts": attempts, "note": note})

    def grant_final_attempts(
        self, enrollment_id: int, attempts: int, note: str | None
    ) -> AttemptGrant:
        return self.grant_step_attempts(enrollment_id, attempts, note)

    # Instructor: contenido, videos y evaluación

    def list_topic_resources(self, topic_id: int) -> list[Resource]:
        del topic_id
        return self._list(Resource, "resources")

    def review_resource(self, resource_id: int, review_status: str) -> Resource:
        resource = self._list(Resource, "resources")[0]
        resource.id = resource_id
        resource.review_status = review_status  # type: ignore[assignment]
        return resource

    def update_resource_content(self, resource_id: int, content: dict[str, Any]) -> Resource:
        resource = self._list(Resource, "resources")[0]
        resource.id = resource_id
        resource.content = content
        return resource

    def regenerate_resource(self, resource_id: int, *, idempotency_key: str) -> JobAccepted:
        del resource_id, idempotency_key
        return self._model(JobAccepted, "job_accepted")

    def list_topic_items(self, topic_id: int) -> Page[ReviewItem]:
        del topic_id
        return self._model(Page[ReviewItem], "items")

    def update_item(self, item_id: int, patch: ItemPatch) -> ReviewItem:
        item = self._model(Page[ReviewItem], "items").items[0]
        item.id = item_id
        if patch.review_status:
            item.review_status = patch.review_status
        return item

    def list_video_candidates(self, topic_id: int) -> TopicVideos:
        del topic_id
        return self._model(TopicVideos, "video_candidates")

    def search_video_candidates(self, topic_id: int, *, idempotency_key: str) -> JobAccepted:
        del topic_id, idempotency_key
        return self._model(JobAccepted, "job_accepted")

    def update_video_candidate(
        self, candidate_id: int, *, status: VideoStatus | None, is_relevant: bool | None
    ) -> VideoCandidate:
        videos = self._model(TopicVideos, "video_candidates")
        candidate = next(
            (c for c in videos.candidates if c.id == candidate_id), videos.candidates[0]
        )
        if status:
            candidate.status = status
        if is_relevant is not None:
            candidate.is_relevant = is_relevant
        return candidate

    def add_video_candidate(
        self, topic_id: int, youtube_video_id: str, title: str
    ) -> VideoCandidate:
        del topic_id
        candidate = self._model(TopicVideos, "video_candidates").candidates[0]
        candidate.youtube_video_id = youtube_video_id
        candidate.title = title
        candidate.origin = "instructor"
        return candidate

    def get_video_quality(self, path_id: int) -> VideoQuality:
        del path_id
        return self._model(VideoQuality, "video_quality")

    def get_annotation_queue(self, course_id: int) -> AnnotationQueue:
        del course_id
        return self._model(AnnotationQueue, "annotation_queue")

    def annotate_item(self, item_id: int, body: AnnotationBody) -> None:
        del item_id, body
        self._doc("annotation_queue")

    def get_grading_queue(self, sample: SampleType) -> GradingQueue:
        queue = self._model(GradingQueue, "grading_queue")
        queue.sample_type = sample
        # Como la API: lo que ya califiqué no vuelve a la cola y suma a lo hecho de la muestra.
        graded = self._graded_answer_ids()
        queue.items = [i for i in queue.items if i.attempt_answer_id not in graded]
        if sample == "random":
            queue.sample_done += len(graded)
        return queue

    def grade_answer(self, attempt_answer_id: int, body: HumanGradingBody) -> HumanGradingResult:
        self._graded_answer_ids().add(attempt_answer_id)
        # La API responde con la forma de `HumanGradingResponse`: eco de lo que calificó el
        # evaluador más la nota del LLM; el adaptador la convierte como con la API real.
        doc = {
            **self._doc("human_grading_result"),
            "attempt_answer_id": attempt_answer_id,
            "criteria": [c.model_dump() for c in body.criteria],
            "score": body.score,
        }
        return _parse(HumanGradingResult, grading_result_from_api(doc))

    def _graded_answer_ids(self) -> set[int]:
        """Eco mínimo de «Guardar»: las respuestas calificadas en esta sesión de fixtures."""
        if not hasattr(self, "_graded"):
            self._graded: set[int] = set()
        return self._graded

    # Administrador

    def list_users(self, *, limit: int = 100, offset: int = 0) -> Page[AdminUser]:
        page = self._model(Page[AdminUser], "users")
        items = page.items[offset : offset + limit]
        return Page[AdminUser](items=items, total=page.total, limit=limit, offset=offset)

    def create_user(self, body: UserCreate) -> AdminUser:
        data = self._doc("user_new")
        return AdminUser.model_validate(
            {**data, "email": body.email, "full_name": body.full_name, "roles": body.roles}
        )

    def set_user_roles(self, user_id: int, roles: Sequence[Role]) -> list[Role]:
        del user_id
        if self.staff_scenario == "last_admin":
            raise ApiError(409, "LAST_ADMIN", "last administrator")
        self._doc("users")
        return list(roles)

    def set_user_active(self, user_id: int, active: bool) -> AdminUser:
        if self.staff_scenario == "last_admin":
            raise ApiError(409, "LAST_ADMIN", "last administrator")
        users = self._model(Page[AdminUser], "users").items
        user = next((u for u in users if u.id == user_id), users[0])
        user.active = active
        return user

    def get_llm_summary(self) -> LlmSummary:
        return self._model(LlmSummary, "llm_summary")

    def list_llm_logs(self, *, limit: int = 50, offset: int = 0) -> Page[LlmCallLog]:
        page = self._model(Page[LlmCallLog], "llm_logs")
        items = page.items[offset : offset + limit]
        return Page[LlmCallLog](items=items, total=page.total, limit=limit, offset=offset)

    def get_evaluation_metrics(self, learning_path_id: int | None = None) -> MetricsEvaluation:
        del learning_path_id
        return self._model(MetricsEvaluation, "metrics")

    def _evaluators(self) -> list[CourseEvaluator]:
        """Eco mínimo de asignar y quitar: los evaluadores activos de esta sesión de fixtures."""
        if not hasattr(self, "_course_evaluators"):
            self._course_evaluators: list[CourseEvaluator] = self._list(
                CourseEvaluator, "course_evaluators"
            )
        return self._course_evaluators

    def list_course_evaluators(self, course_id: int) -> list[CourseEvaluator]:
        return [e for e in self._evaluators() if e.course_id == course_id]

    def assign_course_evaluator(self, course_id: int, user_id: int) -> CourseEvaluator:
        evaluators = self._evaluators()
        if any(e.course_id == course_id and e.user_id == user_id for e in evaluators):
            raise ApiError(409, "CONFLICT", "The user is already an evaluator of the course.")
        created = CourseEvaluator(
            id=max((e.id for e in evaluators), default=0) + 1, course_id=course_id, user_id=user_id
        )
        evaluators.append(created)
        return created

    def remove_course_evaluator(self, evaluator_id: int) -> CourseEvaluator:
        evaluators = self._evaluators()
        found = next((e for e in evaluators if e.id == evaluator_id), None)
        if found is None:
            raise ApiError(404, "NOT_FOUND", "Course evaluator not found.")
        evaluators.remove(found)
        return found

    def list_admin_enrollments(self, *, limit: int = 100, offset: int = 0) -> Page[AdminEnrollment]:
        page = self._model(Page[AdminEnrollment], "admin_enrollments")
        items = page.items[offset : offset + limit]
        return Page[AdminEnrollment](items=items, total=page.total, limit=limit, offset=offset)

    def create_admin_enrollment(self, user_id: int, learning_path_id: int) -> AdminEnrollment:
        del user_id, learning_path_id
        return self._model(Page[AdminEnrollment], "admin_enrollments").items[0]

    def withdraw_enrollment(self, enrollment_id: int, note: str) -> AdminEnrollment:
        del note
        item = self._model(Page[AdminEnrollment], "admin_enrollments").items[0]
        item.id = enrollment_id
        item.status = "withdrawn"
        item.analysis_included = False
        return item

    def move_enrollment(self, enrollment_id: int, learning_path_id: int) -> AdminEnrollment:
        del learning_path_id
        item = self._model(Page[AdminEnrollment], "admin_enrollments").items[0]
        item.id = enrollment_id
        item.analysis_included = False
        return item
