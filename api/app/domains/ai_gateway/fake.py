"""`FakeAiService`: doble del servicio de IA para pruebas y para desarrollo sin `ai/`.

Cumple `AiServicePort`. Los trabajos se resuelven al instante con una salida determinista que
cumple el contrato (`prompts/schemas/*.json`; lo comprueba la prueba de contrato). Las pruebas
pueden dejar un trabajo en `running` (`auto_complete=False`), forzar un fallo o registrar su propia
salida por tipo de trabajo.
"""

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from app.domains.ai_gateway.entities import AiJobError, JobRef, JobRefs, JobStatus
from app.domains.ai_gateway.exceptions import AiJobNotFoundError, AiServiceUnavailableError
from app.domains.ai_gateway.fake_learning import LEARNING_JOB_RESULTS, LEARNING_TASK_RESULTS
from app.domains.content.fake_results import CONTENT_RESULTS

ResultFactory = Callable[[dict[str, Any]], dict[str, Any]]

SYLLABUS_CONTRACT = "syllabus.v1"


def _meta(prompt_id: str, seed: str) -> dict[str, Any]:
    return {
        "prompt_id": prompt_id,
        "prompt_version": "v1",
        "model": "fake-model",
        "generated_at": datetime(2026, 11, 7, 15, 0, tzinfo=UTC).isoformat().replace("+00:00", "Z"),
        "input_sha256": hashlib.sha256(seed.encode()).hexdigest(),
        "from_cache": False,
    }


def fake_syllabus(input_: dict[str, Any]) -> dict[str, Any]:
    """Un syllabus de tres temas encadenados, válido contra `syllabus.v1.json`."""

    def outcome(topic: str, n: int, bloom: str) -> dict[str, str]:
        return {
            "id": f"lo_{topic}_{n}",
            "statement": f"Explicar {topic.replace('_', ' ')} con un ejemplo",
            "bloom_level": bloom,
        }

    topics = [
        ("fundamentals", "Fundamentos", [], "understand", 60),
        ("linear_regression", "Regresión lineal", ["fundamentals"], "apply", 90),
        (
            "logistic_regression",
            "Regresión logística",
            ["fundamentals", "linear_regression"],
            "analyze",
            120,
        ),
    ]
    return {
        "course_key": "machine_learning_basics",
        "course_name": "Fundamentos de Machine Learning",
        "default_objective": (
            "Construir y evaluar modelos supervisados básicos con un criterio medible."
        ),
        "topics": [
            {
                "id": key,
                "name": name,
                "description": f"Descripción de {name}.",
                "subtopics": [f"Subtema de {name}"],
                "learning_outcomes": [outcome(key, 1, bloom)],
                "bloom_level": bloom,
                "prerequisites": prerequisites,
                "estimated_minutes": minutes,
                "is_mandatory": key == "fundamentals",
            }
            for key, name, prerequisites, bloom, minutes in topics
        ],
        "meta": _meta("syllabus_structuring", str(input_.get("syllabus_document_id"))),
    }


def fake_generate_content(_input: dict[str, Any]) -> dict[str, Any]:
    """`course.generate_content` solo orquesta: aquí no encola trabajos hijos."""
    return {"jobs": []}


DEFAULT_RESULTS: dict[str, tuple[str | None, ResultFactory]] = {
    "syllabus.structure": (SYLLABUS_CONTRACT, fake_syllabus),
    "course.generate_content": (None, fake_generate_content),
    **LEARNING_JOB_RESULTS,
}

# Las salidas de los trabajos de contenido las define el dominio `content`.
DEFAULT_RESULTS.update(CONTENT_RESULTS)


@dataclass(frozen=True)
class SubmittedJob:
    job_type: str
    input: dict[str, Any]
    idempotency_key: str
    refs: JobRefs


class FakeAiService:
    def __init__(self, *, auto_complete: bool = True) -> None:
        self.auto_complete = auto_complete
        self.jobs: dict[str, JobStatus] = {}
        self.submitted: list[SubmittedJob] = []
        self.task_results: dict[str, ResultFactory] = dict(LEARNING_TASK_RESULTS)
        self.unavailable = False
        self._by_key: dict[str, str] = {}
        self._factories: dict[str, tuple[str | None, ResultFactory]] = dict(DEFAULT_RESULTS)
        self._failures: dict[str, AiJobError] = {}
        self._inputs: dict[str, dict[str, Any]] = {}

    # --- configuración para pruebas ---------------------------------------------------------
    def set_result(
        self, job_type: str, factory: ResultFactory, *, contract: str | None = None
    ) -> None:
        self._factories[job_type] = (contract, factory)

    def fail_next(
        self, job_type: str, *, code: str = "INVALID_OUTPUT", retryable: bool = True
    ) -> None:
        self._failures[job_type] = AiJobError(
            code=code, message=f"Fake failure {code}.", retryable=retryable
        )

    def complete(self, job_id: str) -> JobStatus:
        """Termina un trabajo que quedó en `running` (con `auto_complete=False`)."""
        job = self.jobs[job_id]
        failure = self._failures.pop(job.job_type, None)
        if (
            failure is None
            and job.job_type == "diagnostic.generate_items"
            and not self._inputs[job_id].get("topic_ids")
        ):
            # El fake no lee la base: con solo `course_id` (el contrato) no puede armar el banco
            # del diagnóstico. Termina como `ai/` ante una referencia que no conoce.
            failure = AiJobError(
                code="INPUT_REFERENCE_NOT_FOUND",
                message="The fake AI service cannot read the course topics.",
                retryable=False,
            )
        now = datetime.now(UTC)
        if failure is not None:
            done = replace(
                job, status="failed", error=failure, attempts=1, finished_at=now, started_at=now
            )
        else:
            contract, factory = self._factories.get(job.job_type, (None, lambda _i: {}))
            done = replace(
                job,
                status="succeeded",
                contract=contract,
                result=factory(self._inputs[job_id]),
                attempts=1,
                cost_usd=0.0,
                started_at=now,
                finished_at=now,
            )
        self.jobs[job_id] = done
        return done

    # --- AiServicePort ----------------------------------------------------------------------
    async def submit_job(
        self,
        job_type: str,
        input: dict[str, Any],
        idempotency_key: str,
        refs: JobRefs | None = None,
    ) -> JobRef:
        self._check_available()
        existing = self._by_key.get(idempotency_key)
        if existing is not None:
            job = self.jobs[existing]
            return JobRef(job.job_id, job.job_type, job.status, job.created_at)
        job_id = str(uuid.uuid4())
        job = JobStatus(
            job_id=job_id,
            job_type=job_type,
            status="queued",
            refs=refs or JobRefs(),
            created_at=datetime.now(UTC),
        )
        self.jobs[job_id] = job
        self._inputs[job_id] = input
        self._by_key[idempotency_key] = job_id
        self.submitted.append(SubmittedJob(job_type, input, idempotency_key, job.refs))
        if self.auto_complete:
            self.complete(job_id)
        else:
            self.jobs[job_id] = replace(job, status="running")
        job = self.jobs[job_id]
        return JobRef(job.job_id, job.job_type, "queued", job.created_at)

    async def get_job(self, job_id: str) -> JobStatus:
        self._check_available()
        job = self.jobs.get(job_id)
        if job is None:
            raise AiJobNotFoundError(job_id)
        return job

    async def list_jobs(
        self,
        *,
        job_type: str | None = None,
        status: str | None = None,
        course_id: int | None = None,
        limit: int = 100,
    ) -> list[JobStatus]:
        self._check_available()
        found = [
            j
            for j in self.jobs.values()
            if (job_type is None or j.job_type == job_type)
            and (status is None or j.status == status)
            and (course_id is None or j.refs.course_id == course_id)
        ]
        return found[:limit]

    async def run_task(
        self,
        task: str,
        input: dict[str, Any],
    ) -> dict[str, Any]:
        self._check_available()
        factory = self.task_results.get(task)
        if factory is None:
            raise NotImplementedError(f"FakeAiService has no result for the task {task}.")
        return factory(input)

    def _check_available(self) -> None:
        if self.unavailable:
            raise AiServiceUnavailableError
