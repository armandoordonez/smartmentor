"""Operaciones del aprendiz que no están en `base.py` y escenarios de fixtures del aprendiz (F07b).

- `LearnerOps`: Protocol con las operaciones nuevas (verificación pública del badge, metas).
- `LearnerApiOps`: implementación HTTP (la mezcla `ApiClient`).
- `LearnerFixtureOps`: implementación de fixtures (la mezcla `FixturesClient`), guiada por un
  `LearnerScript`: qué documento de `tests/fixtures/learner/` devuelve cada operación. No hay reglas
  de negocio: el estado que sigue lo dice el documento (su `next_action`), no el cliente.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from clients.base import ApiError
from clients.models import Enrollment, Job, JobAccepted, NextAction
from clients.models_learner import (
    AttemptSummary,
    BadgeAssertion,
    StudyGoals,
    StudyGoalsUpdate,
)


class LearnerApiOps:
    """Mezcla de `ApiClient`: operaciones HTTP del aprendiz fuera de `base.py`."""

    def _request(self, method: str, path: str, *, json: Any = None) -> httpx.Response:
        raise NotImplementedError  # lo implementa ApiClient

    def get_badge_assertion(self, public_id: str) -> BadgeAssertion:
        # Ruta pública: sin sesión, pero el cliente siempre manda el token (inofensivo).
        response = self._request("GET", f"/badges/{public_id}/assertion.json")
        return BadgeAssertion.model_validate(response.json())

    def list_attempt_history(self, enrollment_id: int, step_id: int | None) -> list[AttemptSummary]:
        """Ruta propuesta (no está en el contrato): intentos calificados del tema o de la final."""
        where = f"steps/{step_id}" if step_id is not None else "final"
        response = self._request("GET", f"/me/enrollments/{enrollment_id}/{where}/attempts")
        return [AttemptSummary.model_validate(item) for item in response.json()]

    def get_badge_image(self, public_id: str) -> bytes:
        return self._request("GET", f"/badges/{public_id}/image.png").content

    def get_study_goals(self) -> StudyGoals | None:
        """Ruta propuesta (no está en el contrato): un 404 significa «sin metas»."""
        try:
            response = self._request("GET", "/me/study-goals")
        except ApiError as error:
            if error.status == 404:
                return None
            raise
        return StudyGoals.model_validate(response.json())

    def set_study_goals(self, update: StudyGoalsUpdate) -> StudyGoals:
        response = self._request("PUT", "/me/study-goals", json=update.model_dump(mode="json"))
        return StudyGoals.model_validate(response.json())


# --- Fixtures ------------------------------------------------------------------------------------

DEFAULT_DOCS: dict[str, str] = {
    "diagnostic": "learner/diagnostic",
    "diagnostic_submit": "learner/job_accepted_diagnostic",
    "diagnostic_result": "learner/diagnostic_result",
    "set_objective": "learner/enrollment_in_path",
    "path": "learner/path",
    "step_content": "learner/step_content",
    "create_attempt": "learner/attempt_topic",
    "attempt": "learner/attempt_topic",
    "submit_attempt": "learner/attempt_result_passed",
    "attempt_result": "learner/attempt_result_passed",
    "final_attempt": "learner/attempt_final",
    "review_plan": "learner/review_plan",
    "badge": "learner/badge",
    "assertion": "learner/assertion",
    "goals": "learner/goals",
    "history": "learner/history_exhausted",
    "history_final": "learner/history_final_exhausted",
    "job_outcome": "done",
}


@dataclass(frozen=True)
class LearnerScript:
    """Documentos que devuelve cada operación. `docs` pisa a `DEFAULT_DOCS`."""

    docs: Mapping[str, str] = field(default_factory=dict)
    offline: bool = False

    def doc(self, operation: str) -> str:
        return self.docs.get(operation, DEFAULT_DOCS[operation])


@dataclass(frozen=True)
class LearnerScenarioSpec:
    key: str
    label: str
    description: str
    enrollments: str
    script: LearnerScript = field(default_factory=LearnerScript)


_E = "learner/enrollments_"

LEARNER_SCENARIOS: tuple[LearnerScenarioSpec, ...] = (
    LearnerScenarioSpec(
        "learner_diagnostic",
        "Diagnóstico en curso (E3)",
        "Pregunta 4 de 15; las tres primeras ya están guardadas.",
        _E + "diagnostic",
    ),
    LearnerScenarioSpec(
        "learner_calculating",
        "Calculando tu nivel (U1a)",
        "El trabajo de IA está en curso y termina en la segunda consulta.",
        _E + "calculating",
    ),
    LearnerScenarioSpec(
        "learner_calculating_error",
        "Error de la IA al calcular (U1a)",
        "El trabajo de IA falla: «Tu avance está guardado».",
        _E + "calculating",
        LearnerScript({"job_outcome": "failed"}),
    ),
    LearnerScenarioSpec(
        "learner_objective",
        "Resultado y objetivo (E4)",
        "Diagnóstico calificado; falta confirmar el objetivo.",
        _E + "objective",
    ),
    LearnerScenarioSpec(
        "learner_path",
        "Ruta personalizada (E5)",
        "Tema 3 de 5 en curso; un tema omitido por el diagnóstico.",
        _E + "path",
    ),
    LearnerScenarioSpec(
        "learner_fixed_path",
        "Ruta fija (E5b)",
        "Grupo de comparación del piloto: sin temas omitidos.",
        _E + "fixed_path",
        LearnerScript({"path": "learner/path_fixed"}),
    ),
    LearnerScenarioSpec(
        "learner_quiz_failed",
        "Quiz no aprobado (E7b)",
        "60 % en el intento 1 de 3.",
        _E + "quiz_failed",
        LearnerScript(
            {
                "attempt": "learner/attempt_topic_failed",
                "attempt_result": "learner/attempt_result_failed",
                "step_content": "learner/step_content_remedial",
            }
        ),
    ),
    LearnerScenarioSpec(
        "learner_exhausted",
        "Intentos agotados del tema (E7c)",
        "Usaste los 3 intentos de Regresión logística.",
        _E + "exhausted",
        LearnerScript(
            {
                "attempt": "learner/attempt_topic_failed",
                "attempt_result": "learner/attempt_result_exhausted",
                "step_content": "learner/step_content_exhausted",
            }
        ),
    ),
    LearnerScenarioSpec(
        "learner_final_ready",
        "Evaluación final disponible (E8)",
        "Todos los temas aprobados; falta la evaluación final.",
        _E + "final_ready",
        LearnerScript(
            {
                "path": "learner/path_all_passed",
                "attempt": "learner/attempt_final",
                "submit_attempt": "learner/attempt_result_final_failed",
                "attempt_result": "learner/attempt_result_final_failed",
            }
        ),
    ),
    LearnerScenarioSpec(
        "learner_final_failed",
        "Final no aprobada (E9)",
        "72 % en la final; temas a repasar.",
        _E + "final_failed",
        LearnerScript(
            {
                "path": "learner/path_all_passed",
                "attempt_result": "learner/attempt_result_final_failed",
            }
        ),
    ),
    LearnerScenarioSpec(
        "learner_final_exhausted",
        "Final con intentos agotados (E9c)",
        "Usaste los 3 intentos de la evaluación final.",
        _E + "final_exhausted",
        LearnerScript(
            {
                "path": "learner/path_all_passed",
                "attempt_result": "learner/attempt_result_final_exhausted",
            }
        ),
    ),
    LearnerScenarioSpec(
        "learner_completed",
        "Ruta completada (E13a, E10)",
        "Badge emitido; falta la encuesta final.",
        _E + "completed",
        LearnerScript(
            {"path": "learner/path_all_passed", "history_final": "learner/history_final_passed"}
        ),
    ),
    LearnerScenarioSpec(
        "learner_badge",
        "Badge obtenido (E10, E12)",
        "Ruta completada con badge y encuesta respondida.",
        _E + "badge",
        LearnerScript(
            {"path": "learner/path_all_passed", "history_final": "learner/history_final_passed"}
        ),
    ),
    LearnerScenarioSpec(
        "learner_offline",
        "Sin conexión",
        "Toda operación del aprendiz responde 503 SERVICE_UNAVAILABLE.",
        _E + "path",
        LearnerScript(offline=True),
    ),
)

LEARNER_SCENARIOS_BY_KEY = {spec.key: spec for spec in LEARNER_SCENARIOS}


# PNG de 1 x 1 píxel para la descarga del badge en el modo `fixtures`.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c63"
    "6060606000000005000150a1a3a60000000049454e44ae426082"
)


@cache
def read_fixture(directory: Path, name: str) -> Any:
    path = directory / f"{name}.json"
    if not path.is_file():
        raise ApiError(404, "NOT_FOUND", f"fixture {name} not found")
    return json.loads(path.read_text(encoding="utf-8"))


class LearnerFixtureOps:
    """Mezcla de `FixturesClient`: lee los documentos del `LearnerScript` de la sesión."""

    _dir: Path
    _script: LearnerScript
    _job_polls: dict[str, int]
    _enrollments: list[Enrollment]

    def echo_next_action(self, action: NextAction | None) -> None:
        """Repite en la inscripción de la sesión lo que dijo la API (eco, sin reglas de negocio)."""
        if action is not None and self._enrollments:
            self._enrollments[0].next_action = action

    def check_online(self) -> None:
        if self._script.offline:
            raise ApiError(503, "SERVICE_UNAVAILABLE", "offline scenario")

    def doc[M: BaseModel](self, operation: str, model: type[M]) -> M:
        self.check_online()
        return model.model_validate(read_fixture(self._dir, self._script.doc(operation)))

    def doc_raw(self, operation: str) -> dict[str, Any]:
        self.check_online()
        data = read_fixture(self._dir, self._script.doc(operation))
        if not isinstance(data, dict):
            raise ApiError(502, "INVALID_RESPONSE", "fixture is not an object")
        return data

    def job_document(self, job_id: str) -> Job:
        """Primera consulta: en curso. Las siguientes: el resultado del escenario.

        Como la API real, el trabajo no trae `next_action`: al terminar, la inscripción de la
        sesión pasa al `next_action` de `learner/after-<job_id>.json` (lo que la API dice después).
        """
        self.check_online()
        polls = self._job_polls.get(job_id, 0)
        self._job_polls[job_id] = polls + 1
        if job_id.startswith("job-"):
            stage = "running" if polls == 0 else self._script.doc("job_outcome")
            job = Job.model_validate(read_fixture(self._dir, f"learner/{job_id}_{stage}"))
            if job.status == "succeeded":
                after = read_fixture(self._dir, f"learner/after-{job_id}")
                self.echo_next_action(NextAction.model_validate(after))
            return job
        name = "job_running" if polls == 0 else "job_succeeded"
        job = Job.model_validate(read_fixture(self._dir, name))
        job.job_id = job_id
        return job

    def accepted(self, operation: str) -> JobAccepted:
        return self.doc(operation, JobAccepted)

    def job_succeeded(self, job_id: str) -> bool:
        """El trabajo ya se consultó hasta terminar bien (p. ej., el banco de preguntas listo)."""
        return self._job_polls.get(job_id, 0) >= 2 and self._script.doc("job_outcome") == "done"

    def get_badge_assertion(self, public_id: str) -> BadgeAssertion:
        del public_id
        return self.doc("assertion", BadgeAssertion)

    def list_attempt_history(self, enrollment_id: int, step_id: int | None) -> list[AttemptSummary]:
        del enrollment_id
        self.check_online()
        name = self._script.doc("history_final" if step_id is None else "history")
        return [AttemptSummary.model_validate(item) for item in read_fixture(self._dir, name)]

    def get_badge_image(self, public_id: str) -> bytes:
        del public_id
        self.check_online()
        return TINY_PNG

    def get_study_goals(self) -> StudyGoals | None:
        saved: StudyGoals | None = getattr(self, "_saved_goals", None)
        return saved.model_copy() if saved else self.doc("goals", StudyGoals)

    def set_study_goals(self, update: StudyGoalsUpdate) -> StudyGoals:
        goals = self.doc("goals", StudyGoals)
        goals.daily_minutes_goal = update.daily_minutes_goal
        goals.monthly_topics_goal = update.monthly_topics_goal
        self._saved_goals = goals  # eco del estado de la sesión de demostración
        return goals
