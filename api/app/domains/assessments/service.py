"""Casos de uso de evaluaciones: diagnóstico, objetivo, intentos, calificación, final y badge.

Reglas (plan 5.3.4): el diagnóstico se arma desde el banco aprobado (sin LLM); cada intento toma
ítems que el aprendiz no ha visto; opción múltiple por regla y respuesta corta por criterios
(`grading.short_answer`); los intentos extra se reportan aparte; la final exige todos los pasos
`passed` o `skipped`; el badge solo se emite con la final aprobada.

**Trabajos de `ai/` sin columna propia.** El esquema v2.0.0 no guarda el `job_id` en
`diagnostics` ni en `attempt_answers`. Cada trabajo usa una `idempotency_key` determinista
(`<tarea>:<entidad>:<id>:<versión>`) y una entrada que se puede reconstruir; para volver a obtener
el `job_id` se repite el envío, que en `ai/` devuelve el mismo trabajo (ADR 0010). Ver `JobLocator`.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError

from app.common.entities import require_id
from app.common.exceptions import (
    BusinessRuleError,
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
)
from app.common.unit_of_work import UnitOfWork
from app.core.config import get_settings
from app.domains.ai_gateway.entities import JobRef, JobRefs, JobStatus, PendingJob
from app.domains.ai_gateway.exceptions import AiResultInvalidError, AiServiceUnavailableError
from app.domains.ai_gateway.repository import AiServicePort
from app.domains.assessments import badges
from app.domains.assessments.contracts import (
    AssessmentItemBankV1,
    DiagnosticFinalizationV1,
    DiagnosticResultV1,
    GradingV1,
)
from app.domains.assessments.entities import (
    AssessmentAttempt,
    AssessmentItem,
    AttemptAnswer,
    Badge,
    Diagnostic,
)
from app.domains.assessments.grading import (
    SHORT_ANSWER,
    attempt_score,
    grade_multiple_choice,
    pick_quiz_items,
    round_robin,
    short_answer_is_correct,
)
from app.domains.assessments.repository import (
    AnswerRepository,
    AttemptRepository,
    BadgeRepository,
    ContentReader,
    DiagnosticRepository,
    ItemRepository,
    SurveyLookup,
)
from app.domains.courses.entities import Course
from app.domains.identity.authentication import CurrentUser
from app.domains.identity.entities import UserProfile
from app.domains.learning_paths import exceptions as path_errors
from app.domains.learning_paths.entities import (
    DEFAULT_SHORT_ANSWER_MIN_RATIO,
    Enrollment,
    LearningPath,
    PathStep,
    TopicNode,
)
from app.domains.learning_paths.repository import (
    AlertRepository,
    AttemptGrantRepository,
    EnrollmentRepository,
    PathRepository,
    PathStepRepository,
    PlatformReader,
)
from app.domains.learning_paths.service import (
    AttemptSummary,
    LearnerHistory,
    PathProgress,
    is_staff_owner,
)
from app.domains.learning_paths.states import (
    OPEN_ATTEMPTS,
    AlertType,
    AttemptStatus,
    EnrollmentStatus,
    NextAction,
    ProgressFacts,
    StepState,
    StepStatus,
    check_attempt_transition,
    is_closed,
    next_action,
)

logger = logging.getLogger("app.assessments")

DIAGNOSTIC_FINALIZE = "diagnostic.finalize"
GRADING_SHORT_ANSWER = "grading.short_answer"
QUIZ_BANK = "items.generate_quiz_bank"
FINAL_BANK = "items.generate_final_bank"
LEVELS_ESTIMATE = "levels.estimate"

ITEMS_PER_ATTEMPT = 5  # quiz del tema (ADR 0015: 3 intentos x 5 ítems)
FINAL_ITEMS = 10
FINAL_ON_DEMAND_SHORT_ANSWERS = 1
DIAGNOSTIC_ITEMS_PER_TOPIC = 3
REINFORCE_CUTOFF = 50.0
OPEN_DIAGNOSTIC = ("created", "in_progress", "scoring_failed")


@dataclass
class Repos:
    """Repositorios que usan los casos de uso de evaluaciones (rutas y evaluaciones)."""

    paths: PathRepository
    enrollments: EnrollmentRepository
    steps: PathStepRepository
    grants: AttemptGrantRepository
    alerts: AlertRepository
    reader: PlatformReader
    items: ItemRepository
    diagnostics: DiagnosticRepository
    attempts: AttemptRepository
    answers: AnswerRepository
    badges: BadgeRepository
    content: ContentReader
    surveys: SurveyLookup


@dataclass(frozen=True)
class LearnerAnswerInput:
    item_id: int
    selected_option: int | None = None
    dont_know: bool = False
    text_answer: str | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _resume_text(profile: UserProfile | None) -> str | None:
    """Hoja de vida seudonimizada: solo campos estructurados, sin nombre ni correo (DEF-05)."""
    if profile is None:
        return None
    parts = [
        f"{label}: {value}"
        for label, value in (
            ("education_level", profile.education_level),
            ("qualification_title", profile.qualification_title),
            ("job_title", profile.job_title),
            ("experience_band", profile.experience_band),
            ("tools", ", ".join(str(t) for t in profile.tools) if profile.tools else None),
        )
        if value
    ]
    return "; ".join(parts) or None


def _short_answer_ratio(path: LearningPath) -> float:
    ratio = path.short_answer_min_ratio
    return ratio if 0 < ratio <= 1 else DEFAULT_SHORT_ANSWER_MIN_RATIO


# --- localizador de trabajos ------------------------------------------------------------------


class JobLocator:
    """Obtiene (o crea, si faltara) el trabajo de una entidad repitiendo su envío idempotente."""

    def __init__(self, ai: AiServicePort) -> None:
        self._ai = ai

    async def finalize_job(self, enrollment: Enrollment, course_id: int) -> JobRef | None:
        snapshot = enrollment.profile_snapshot or {}
        key, payload = snapshot.get("finalize_key"), snapshot.get("finalize_input")
        if not key or not isinstance(payload, dict):
            return None
        return await self._ai.submit_job(
            DIAGNOSTIC_FINALIZE,
            payload,
            str(key),
            JobRefs(course_id=course_id, enrollment_id=require_id(enrollment)),
        )

    @staticmethod
    def grading_input(answer: AttemptAnswer, item: AssessmentItem, ratio: float) -> dict[str, Any]:
        return {
            "item_id": str(item.id),
            "stem": item.stem,
            "model_answer": item.model_answer or "",
            "rubric": [
                {"criterion": str(c.get("criterion", "")), "points": float(c.get("points", 0))}
                for c in (item.rubric or [])
            ],
            "answer_text": answer.text_answer or "",
            "min_criteria_ratio": round(ratio, 4),
        }

    async def grading_job(
        self, answer: AttemptAnswer, item: AssessmentItem, ratio: float, enrollment_id: int
    ) -> JobRef:
        return await self._ai.submit_job(
            GRADING_SHORT_ANSWER,
            self.grading_input(answer, item, ratio),
            f"{GRADING_SHORT_ANSWER}:attempt_answer:{require_id(answer)}:v1",
            JobRefs(topic_id=item.topic_id, enrollment_id=enrollment_id),
        )


# --- base común --------------------------------------------------------------------------------


class _Base:
    def __init__(self, repos: Repos, ai: AiServicePort, uow: UnitOfWork) -> None:
        self._r = repos
        self._ai = ai
        self._uow = uow
        self._jobs = JobLocator(ai)
        self._progress = PathProgress(
            repos.enrollments, repos.steps, repos.alerts, repos.reader, ai
        )

    async def _own_enrollment(
        self, user: CurrentUser, enrollment_id: int, *, for_update: bool = False
    ) -> Enrollment:
        getter = self._r.enrollments.get_for_update if for_update else self._r.enrollments.get
        enrollment = await getter(enrollment_id)
        if enrollment is None or enrollment.user_id != user.id or not enrollment.active:
            raise path_errors.enrollment_not_found(enrollment_id)
        return enrollment

    async def _path(self, enrollment: Enrollment) -> LearningPath:
        path = await self._r.paths.get(enrollment.learning_path_id)
        if path is None:
            raise path_errors.path_not_found(enrollment.learning_path_id)
        return path

    async def _course(self, path: LearningPath) -> Course:
        course = await self._r.reader.course(path.course_id)
        if course is None:
            raise NotFoundError("Course", path.course_id, code="COURSE_NOT_FOUND")
        return course

    async def can_see(self, enrollment_id: int | None, user: CurrentUser) -> bool:
        """El aprendiz dueño de la inscripción o el instructor del curso (o un admin)."""
        if enrollment_id is None:
            return False
        enrollment = await self._r.enrollments.get(enrollment_id)
        if enrollment is None:
            return False
        if enrollment.user_id == user.id:
            return True
        path = await self._r.paths.get(enrollment.learning_path_id)
        return path is not None and is_staff_owner(
            user, await self._r.reader.course(path.course_id)
        )

    async def topic_names(self, enrollment_id: int) -> dict[int, str]:
        """Nombre de cada tema de la ruta de la inscripción (para mostrar «Tema · …»)."""
        enrollment = await self._r.enrollments.get(enrollment_id)
        if enrollment is None:
            return {}
        path = await self._path(enrollment)
        return {n.id: n.name for n in await self._r.reader.topic_nodes(path.course_id)}

    async def _final_counters(self, enrollment: Enrollment, path: LearningPath) -> tuple[int, int]:
        """(intentos de la final usados, máximo con los extra)."""
        attempts = await self._r.attempts.list_for_enrollment(require_id(enrollment))
        used = sum(
            1 for a in attempts if a.assessment_type == "final" and a.status not in OPEN_ATTEMPTS
        )
        granted = await self._r.grants.final_attempts_granted(require_id(enrollment))
        return used, path.max_attempts + granted


# --- progreso (puertos ProgressReader y AssessmentHistory) -------------------------------------


class LearnerProgress(_Base):
    async def facts(self, enrollment: Enrollment, steps: list[PathStep]) -> ProgressFacts:
        path = await self._path(enrollment)
        diagnostic = await self._r.diagnostics.by_enrollment(require_id(enrollment))
        diagnostic_job: str | None = None
        if diagnostic is not None and diagnostic.status == "scoring":
            ref = await self._jobs.finalize_job(enrollment, path.course_id)
            diagnostic_job = ref.job_id if ref is not None else None
        attempts = await self._r.attempts.list_for_enrollment(require_id(enrollment))
        open_attempt = next((a for a in reversed(attempts) if a.status in OPEN_ATTEMPTS), None)
        grading = next((a for a in attempts if a.status == AttemptStatus.GRADING), None)
        grading_job = await self._first_grading_job(grading, enrollment, path) if grading else None
        finals = [a for a in attempts if a.assessment_type == "final"]
        graded_finals = [a for a in finals if a.status == AttemptStatus.GRADED]
        last_final = graded_finals[-1] if graded_finals else None
        used, maximum = await self._final_counters(enrollment, path)
        return ProgressFacts(
            status=enrollment.status,
            diagnostic_status=diagnostic.status if diagnostic is not None else None,
            diagnostic_job_id=diagnostic_job,
            steps=tuple(
                StepState(require_id(s), s.topic_id, s.step_order, s.status) for s in steps
            ),
            open_attempt_id=open_attempt.id if open_attempt else None,
            open_attempt_step_id=open_attempt.path_step_id if open_attempt else None,
            grading_attempt_id=grading.id if grading else None,
            grading_job_id=grading_job,
            last_final_attempt_id=last_final.id if last_final else None,
            last_final_passed=last_final.passed if last_final else None,
            final_attempts_remaining=max(maximum - used, 0),
            has_survey=await self._r.surveys.has_final_survey(require_id(enrollment)),
        )

    async def _first_grading_job(
        self, attempt: AssessmentAttempt, enrollment: Enrollment, path: LearningPath
    ) -> str | None:
        answers = await self._r.answers.list_for_attempt(require_id(attempt))
        items = await self._r.items.by_ids([a.assessment_item_id for a in answers])
        for answer in answers:
            item = items.get(answer.assessment_item_id)
            if item is not None and item.item_type == SHORT_ANSWER and answer.grader is None:
                ref = await self._jobs.grading_job(
                    answer, item, _short_answer_ratio(path), require_id(enrollment)
                )
                return ref.job_id
        return None

    async def next_action_of(self, enrollment: Enrollment) -> NextAction:
        steps = await self._r.steps.list_for_enrollment(require_id(enrollment))
        return next_action(await self.facts(enrollment, steps))

    async def history(self, enrollment_id: int) -> LearnerHistory:
        diagnostic = await self._r.diagnostics.by_enrollment(enrollment_id)
        levels = (
            list((diagnostic.level_by_topic or {}).get("level_by_topic", [])) if diagnostic else []
        )
        attempts = await self._r.attempts.list_for_enrollment(enrollment_id)
        return LearnerHistory(
            level_by_topic=levels,
            attempts=[
                AttemptSummary(
                    id=require_id(a),
                    assessment_type=a.assessment_type,
                    path_step_id=a.path_step_id,
                    attempt_number=a.attempt_number,
                    status=a.status,
                    score=a.score,
                    passed=a.passed,
                    uses_extra_grant=a.uses_extra_grant,
                    submitted_at=a.submitted_at,
                )
                for a in attempts
            ],
        )


# --- diagnóstico y objetivo --------------------------------------------------------------------


@dataclass(frozen=True)
class DiagnosticView:
    diagnostic: Diagnostic
    items: list[AssessmentItem]


@dataclass(frozen=True)
class DiagnosticResultView:
    enrollment: Enrollment
    diagnostic: Diagnostic
    topic_names: dict[int, str]


class DiagnosticService(_Base):
    async def _diagnostic_items(self, nodes: list[TopicNode]) -> list[AssessmentItem]:
        bank = await self._r.items.approved([n.id for n in nodes], "diagnostic")
        picked: list[AssessmentItem] = []
        for node in nodes:
            picked += [i for i in bank if i.topic_id == node.id][:DIAGNOSTIC_ITEMS_PER_TOPIC]
        return picked

    async def start(self, user: CurrentUser, enrollment_id: int) -> DiagnosticView:
        """Arma la prueba desde el banco aprobado (sin LLM, E3)."""
        enrollment = await self._own_enrollment(user, enrollment_id, for_update=True)
        if enrollment.status in (EnrollmentStatus.ENROLLED, EnrollmentStatus.PROFILING):
            profile = await self._r.reader.profile(user.id)
            if profile is None or not profile.has_description:
                raise BusinessRuleError(
                    "The profile description is required before the diagnostic.",
                    code="PROFILE_INCOMPLETE",
                    extra={"missing": ["description"]},
                )
            enrollment = await self._progress.set_enrollment_status(
                enrollment, EnrollmentStatus.DIAGNOSING, profile_description=profile.description
            )
        elif enrollment.status != EnrollmentStatus.DIAGNOSING:
            raise InvalidStateTransitionError("The enrollment is not waiting for a diagnostic.")
        if await self._r.diagnostics.by_enrollment(enrollment_id) is not None:
            raise ConflictError(
                "The enrollment already has a diagnostic.", code="DIAGNOSTIC_ALREADY_EXISTS"
            )
        path = await self._path(enrollment)
        items = await self._diagnostic_items(await self._r.reader.topic_nodes(path.course_id))
        if not items:
            raise ConflictError(
                "The course has no approved diagnostic items.", code="DIAGNOSTIC_BANK_EMPTY"
            )
        diagnostic = await self._r.diagnostics.add(
            Diagnostic(enrollment_id=enrollment_id, item_ids=[require_id(i) for i in items])
        )
        await self._uow.commit()
        return DiagnosticView(diagnostic, items)

    async def _own_diagnostic(
        self, user: CurrentUser, enrollment_id: int, *, for_update: bool = False
    ) -> Diagnostic:
        await self._own_enrollment(user, enrollment_id, for_update=for_update)
        diagnostic = await self._r.diagnostics.by_enrollment(enrollment_id, for_update=for_update)
        if diagnostic is None:
            raise NotFoundError("Diagnostic", enrollment_id)
        return diagnostic

    async def get(self, user: CurrentUser, enrollment_id: int) -> DiagnosticView:
        diagnostic = await self._own_diagnostic(user, enrollment_id)
        items = await self._r.items.by_ids(list(diagnostic.item_ids or []))
        return DiagnosticView(
            diagnostic, [items[i] for i in diagnostic.item_ids or [] if i in items]
        )

    async def save_answers(
        self, user: CurrentUser, enrollment_id: int, answers: list[LearnerAnswerInput]
    ) -> int:
        """Guardado parcial: reemplaza las respuestas por `item_id`."""
        diagnostic = await self._own_diagnostic(user, enrollment_id, for_update=True)
        if diagnostic.status not in OPEN_DIAGNOSTIC:
            raise ConflictError(
                "The diagnostic was already submitted.", code="DIAGNOSTIC_ALREADY_SUBMITTED"
            )
        allowed = set(diagnostic.item_ids or [])
        _check_items(answers, allowed)
        merged = dict(diagnostic.answers or {})
        for answer in answers:
            merged[str(answer.item_id)] = {
                "selected_option": answer.selected_option,
                "dont_know": answer.dont_know,
                "text_answer": answer.text_answer,
            }
        status = "in_progress" if diagnostic.status == "created" else diagnostic.status
        await self._r.diagnostics.update(
            require_id(diagnostic), {"answers": merged, "status": status}
        )
        await self._uow.commit()
        return len(answers)

    async def submit(self, user: CurrentUser, enrollment_id: int) -> JobRef:
        """Entrega el diagnóstico y crea `diagnostic.finalize` (nivel y objetivo propuesto)."""
        enrollment = await self._own_enrollment(user, enrollment_id, for_update=True)
        diagnostic = await self._r.diagnostics.by_enrollment(enrollment_id, for_update=True)
        if diagnostic is None:
            raise NotFoundError("Diagnostic", enrollment_id)
        if (
            diagnostic.status not in OPEN_DIAGNOSTIC
            or enrollment.status != EnrollmentStatus.DIAGNOSING
        ):
            raise ConflictError(
                "The diagnostic was already submitted.", code="DIAGNOSTIC_ALREADY_SUBMITTED"
            )
        path = await self._path(enrollment)
        course = await self._course(path)
        nodes = await self._r.reader.topic_nodes(path.course_id)
        profile = await self._r.reader.profile(enrollment.user_id)
        items = await self._r.items.by_ids(list(diagnostic.item_ids or []))
        stored = diagnostic.answers or {}
        payload: dict[str, Any] = {
            "topic_ids": [str(n.id) for n in nodes],
            "items": [
                {
                    "item_id": str(item_id),
                    "topic_id": str(items[item_id].topic_id),
                    "item_type": items[item_id].item_type,
                    "difficulty": items[item_id].difficulty,
                    "correct_option": items[item_id].correct_index,
                }
                for item_id in diagnostic.item_ids or []
                if item_id in items
            ],
            "answers": [
                {
                    "item_id": str(item_id),
                    "selected_option": (stored.get(str(item_id)) or {}).get("selected_option"),
                    "dont_know": bool((stored.get(str(item_id)) or {}).get("dont_know", False)),
                    "text_answer": (stored.get(str(item_id)) or {}).get("text_answer"),
                }
                for item_id in diagnostic.item_ids or []
                if item_id in items
            ],
            "profile_text": profile.description if profile and profile.has_description else None,
            "resume_text": _resume_text(profile),
            "weights": path.weights,
            "thresholds": {
                "mastery_skip_threshold": path.mastery_skip_threshold,
                "reinforce_cutoff": REINFORCE_CUTOFF,
            },
        }
        parts = path.default_objective_parts
        if parts is not None:
            payload |= {
                "objective_mode": "path_default",
                "path_objective": " ".join(parts.values()),
                "path_objective_parts": parts,
            }
        else:
            payload |= {
                "objective_mode": "llm",
                "path_objective": course.description or course.name,
            }
        submitted_at = _now()
        key = f"{DIAGNOSTIC_FINALIZE}:enrollment:{enrollment_id}:{int(submitted_at.timestamp())}"
        snapshot = {
            "profile_text": payload["profile_text"],
            "resume_text": payload["resume_text"],
            "finalize_key": key,
            "finalize_input": payload,
        }
        ref = await self._ai.submit_job(
            DIAGNOSTIC_FINALIZE,
            payload,
            key,
            JobRefs(course_id=path.course_id, enrollment_id=enrollment_id),
        )
        await self._r.enrollments.update(enrollment_id, {"profile_snapshot": snapshot})
        await self._r.diagnostics.update(
            require_id(diagnostic), {"status": "scoring", "submitted_at": submitted_at}
        )
        await self._uow.commit()
        return ref

    async def result(self, user: CurrentUser, enrollment_id: int) -> DiagnosticResultView:
        enrollment = await self._own_enrollment(user, enrollment_id)
        diagnostic = await self._r.diagnostics.by_enrollment(enrollment_id)
        if diagnostic is None or diagnostic.status != "scored":
            extra: dict[str, Any] = {}
            if diagnostic is not None and diagnostic.status == "scoring":
                path = await self._path(enrollment)
                ref = await self._jobs.finalize_job(enrollment, path.course_id)
                if ref is not None:
                    extra["job_id"] = ref.job_id
            raise ConflictError(
                "The diagnostic result is not ready.", code="DIAGNOSTIC_NOT_READY", extra=extra
            )
        path = await self._path(enrollment)
        names = {n.id: n.name for n in await self._r.reader.topic_nodes(path.course_id)}
        return DiagnosticResultView(enrollment, diagnostic, names)

    async def confirm_objective(
        self, user: CurrentUser, enrollment_id: int, parts: dict[str, str | None]
    ) -> Enrollment:
        """Objetivo en tres partes (E4, E4b): llama a `path.sequence` y crea los pasos."""
        missing = [
            k for k in ("bloom_verb", "content", "criterion") if not (parts.get(k) or "").strip()
        ]
        if missing:
            raise BusinessRuleError(
                "The objective needs a Bloom verb, a content and a measurable criterion.",
                code="OBJECTIVE_NOT_MEASURABLE",
                extra={"missing": missing},
            )
        enrollment = await self._own_enrollment(user, enrollment_id, for_update=True)
        if enrollment.status != EnrollmentStatus.OBJECTIVE_PENDING:
            raise InvalidStateTransitionError("The enrollment is not waiting for an objective.")
        diagnostic = await self._r.diagnostics.by_enrollment(enrollment_id)
        data = (diagnostic.level_by_topic or {}) if diagnostic is not None else {}
        levels = {
            int(t["topic_id"]): float(t["level"])
            for t in data.get("level_by_topic", [])
            if str(t.get("topic_id", "")).isdigit()
        }
        focus = [int(t) for t in data.get("focus_topic_ids", []) if str(t).isdigit()]
        chosen = {k: str(parts[k]).strip() for k in ("bloom_verb", "content", "criterion")}
        proposed = {
            "bloom_verb": enrollment.objective_bloom_verb,
            "content": enrollment.objective_content,
            "criterion": enrollment.objective_criterion,
        }
        origin = (
            enrollment.objective_origin or "llm_proposed"
            if chosen == proposed
            else "learner_edited"
        )
        path = await self._path(enrollment)
        sequenced = await self._progress.sequence(enrollment, path, levels, focus)
        enrollment = await self._progress.set_enrollment_status(
            enrollment,
            EnrollmentStatus.IN_PATH,
            objective_bloom_verb=chosen["bloom_verb"],
            objective_content=chosen["content"],
            objective_criterion=chosen["criterion"],
            objective_origin=origin,
        )
        await self._progress.create_steps(enrollment, path, sequenced)
        await self._uow.commit()
        refreshed = await self._r.enrollments.get(enrollment_id)
        assert refreshed is not None  # noqa: S101
        return refreshed

    # --- ingesta de `diagnostic.finalize` ---------------------------------------------------

    async def ingest_finalization(self, job: JobStatus, result: BaseModel) -> bool:
        assert isinstance(result, DiagnosticFinalizationV1)  # noqa: S101
        enrollment_id = job.refs.enrollment_id
        enrollment = (
            await self._r.enrollments.get_for_update(enrollment_id) if enrollment_id else None
        )
        diagnostic = (
            await self._r.diagnostics.by_enrollment(enrollment_id, for_update=True)
            if enrollment_id
            else None
        )
        if enrollment is None or diagnostic is None or diagnostic.status != "scoring":
            await self._uow.commit()
            return False
        path = await self._path(enrollment)
        current = await self._jobs.finalize_job(enrollment, path.course_id)
        if current is None or current.job_id != job.job_id:
            await self._uow.commit()  # un trabajo superado por una entrega posterior
            return False
        topics = {str(n.id) for n in await self._r.reader.topic_nodes(path.course_id)}
        levels = result.diagnostic_result
        if not {t.topic_id for t in levels.level_by_topic} <= topics:
            raise AiResultInvalidError(job.job_id)
        objective = result.objective
        stored = levels.model_dump(mode="json")
        stored["focus_topic_ids"] = [t for t in objective.focus_topics if t in topics]
        await self._r.diagnostics.update(
            require_id(diagnostic),
            {"status": "scored", "scored_at": _now(), "level_by_topic": stored},
        )
        await self._progress.set_enrollment_status(
            enrollment,
            EnrollmentStatus.OBJECTIVE_PENDING,
            objective_bloom_verb=objective.bloom_verb[:60],
            objective_content=objective.content,
            objective_criterion=objective.criterion,
            objective_origin=objective.origin,
        )
        await self._uow.commit()
        return True

    async def finalization_failed(self, job: JobStatus) -> None:
        enrollment_id = job.refs.enrollment_id
        if enrollment_id is not None:
            diagnostic = await self._r.diagnostics.by_enrollment(enrollment_id, for_update=True)
            if diagnostic is not None and diagnostic.status == "scoring":
                await self._r.diagnostics.update(
                    require_id(diagnostic), {"status": "scoring_failed"}
                )
        await self._uow.commit()

    async def pending_finalizations(self) -> list[PendingJob]:
        pending: list[PendingJob] = []
        for diagnostic in await self._r.diagnostics.list_by_status("scoring"):
            enrollment = await self._r.enrollments.get(diagnostic.enrollment_id)
            path = await self._r.paths.get(enrollment.learning_path_id) if enrollment else None
            if enrollment is None or path is None:
                continue
            ref = await self._jobs.finalize_job(enrollment, path.course_id)
            if ref is not None and (await self._ai.get_job(ref.job_id)).is_finished:
                pending.append(PendingJob(job_id=ref.job_id, job_type=DIAGNOSTIC_FINALIZE))
        return pending


def _check_items(answers: list[LearnerAnswerInput], allowed: set[int]) -> None:
    unknown = sorted({a.item_id for a in answers} - allowed)
    if unknown:
        raise BusinessRuleError(
            "Some answers refer to items that are not part of this assessment.",
            code="VALIDATION_ERROR",
        )


# --- recálculo al cambiar el perfil (E15) -------------------------------------------------------


class ProfileRecalculation(_Base):
    """`ProfileChangeListener` de identidad: recalcula niveles y pasos pendientes (E15)."""

    async def on_profile_changed(self, user_id: int) -> list[int]:
        recalculated: list[int] = []
        enrollments, _ = await self._r.enrollments.list_for_user(user_id, limit=100, offset=0)
        profile = await self._r.reader.profile(user_id)
        for enrollment in enrollments:
            if is_closed(enrollment.status):
                continue
            try:
                if await self._recalculate(enrollment, profile):
                    recalculated.append(require_id(enrollment))
            except (AiServiceUnavailableError, AiResultInvalidError) as exc:
                logger.warning(
                    "profile recalculation skipped",
                    extra={"code": exc.code, "enrollment_id": enrollment.id},
                )
        return recalculated

    async def _recalculate(self, enrollment: Enrollment, profile: UserProfile | None) -> bool:
        if enrollment.status in (EnrollmentStatus.ENROLLED, EnrollmentStatus.PROFILING):
            if profile is None or not profile.has_description:
                return False
            await self._progress.set_enrollment_status(
                enrollment, EnrollmentStatus.DIAGNOSING, profile_description=profile.description
            )
            return True
        if enrollment.status not in (EnrollmentStatus.OBJECTIVE_PENDING, EnrollmentStatus.IN_PATH):
            return False
        snapshot = enrollment.profile_snapshot or {}
        stored_input = snapshot.get("finalize_input")
        diagnostic = await self._r.diagnostics.by_enrollment(require_id(enrollment))
        if (
            not isinstance(stored_input, dict)
            or diagnostic is None
            or diagnostic.status != "scored"
        ):
            return False
        path = await self._path(enrollment)
        payload = {
            k: v
            for k, v in stored_input.items()
            if k not in ("objective_mode", "path_objective", "path_objective_parts")
        }
        payload["profile_text"] = (
            profile.description if profile and profile.has_description else None
        )
        payload["resume_text"] = _resume_text(profile)
        payload["weights"] = path.weights
        try:
            levels = DiagnosticResultV1.model_validate(
                await self._ai.run_task(LEVELS_ESTIMATE, payload)
            )
        except ValidationError as exc:
            raise AiResultInvalidError(LEVELS_ESTIMATE) from exc
        focus = (diagnostic.level_by_topic or {}).get("focus_topic_ids", [])
        stored = levels.model_dump(mode="json") | {"focus_topic_ids": focus}
        await self._r.diagnostics.update(require_id(diagnostic), {"level_by_topic": stored})
        await self._r.enrollments.update(
            require_id(enrollment),
            {
                "profile_description": payload["profile_text"],
                "profile_snapshot": snapshot
                | {"profile_text": payload["profile_text"], "resume_text": payload["resume_text"]},
            },
        )
        if enrollment.status == EnrollmentStatus.IN_PATH:
            values = {
                int(t.topic_id): t.level for t in levels.level_by_topic if t.topic_id.isdigit()
            }
            sequenced = await self._progress.sequence(
                enrollment, path, values, [int(t) for t in focus if str(t).isdigit()]
            )
            await self._progress.resequence(enrollment, path, sequenced)
        return True


# --- intentos, calificación, final y badge -----------------------------------------------------


@dataclass(frozen=True)
class AttemptView:
    attempt: AssessmentAttempt
    items: list[AssessmentItem]
    answers: list[AttemptAnswer]


@dataclass(frozen=True)
class AttemptOutcome:
    """Resultado de crear o entregar un intento: el intento, su resultado o un trabajo de IA."""

    view: AttemptView | None = None
    result: "AttemptResultView | None" = None
    job: JobRef | None = None


@dataclass(frozen=True)
class AttemptResultView:
    attempt: AssessmentAttempt
    pass_threshold: float
    answers: list[tuple[AttemptAnswer, AssessmentItem | None]]
    attempts_used: int
    attempts_max: int
    remedial_resource_id: int | None
    next_action: NextAction


@dataclass(frozen=True)
class StepContentView:
    step: PathStep
    topic: TopicNode
    outcomes: list[dict[str, Any]]
    explanation: dict[str, Any] | None
    personal_example: dict[str, Any] | None
    video: dict[str, Any] | None
    pass_threshold: float
    short_answer_ratio: float
    max_attempts: int


@dataclass(frozen=True)
class AttemptHistoryEntry:
    attempt_id: int
    number: int
    score: float
    correct: int
    total: int
    extra_grant: bool
    passed: bool


@dataclass(frozen=True)
class WeakTopic:
    topic_id: int
    name: str
    score: float
    resource_id: int | None


@dataclass(frozen=True)
class BadgeView:
    badge: Badge
    enrollment: Enrollment
    path: LearningPath
    course: Course


class AttemptService(_Base):
    async def _own_step(
        self, user: CurrentUser, enrollment_id: int, step_id: int, *, for_update: bool = False
    ) -> tuple[Enrollment, PathStep]:
        enrollment = await self._own_enrollment(user, enrollment_id, for_update=for_update)
        step = await self._r.steps.get(step_id)
        if step is None or step.enrollment_id != enrollment_id or not step.active:
            raise path_errors.step_not_found(step_id)
        return enrollment, step

    async def _topic(self, path: LearningPath, topic_id: int) -> TopicNode:
        for node in await self._r.reader.topic_nodes(path.course_id):
            if node.id == topic_id:
                return node
        raise NotFoundError("Topic", topic_id, code="TOPIC_NOT_FOUND")

    async def step_content(
        self, user: CurrentUser, enrollment_id: int, step_id: int
    ) -> StepContentView:
        """Explicación aprobada, video en uso (o respaldo), reglas del quiz e intentos (E6)."""
        enrollment, step = await self._own_step(user, enrollment_id, step_id, for_update=True)
        if step.status in (
            StepStatus.BLOCKED,
            StepStatus.SKIPPED,
            StepStatus.ON_HOLD,
            StepStatus.PASSED,
        ):
            raise path_errors.step_not_available(step.status)
        if step.status == StepStatus.PENDING and enrollment.status == EnrollmentStatus.IN_PATH:
            # Abrir el tema no consume intentos.
            step = await self._progress.set_step_status(step, StepStatus.IN_PROGRESS)
            await self._uow.commit()
        path = await self._path(enrollment)
        return StepContentView(
            step=step,
            topic=await self._topic(path, step.topic_id),
            outcomes=await self._r.content.outcomes(step.topic_id),
            explanation=await self._r.content.explanation(step.topic_id),
            personal_example=await self._r.content.personal_example(step.topic_id, enrollment_id),
            video=await self._r.content.video(step.topic_id),
            pass_threshold=path.topic_pass_threshold,
            short_answer_ratio=_short_answer_ratio(path),
            max_attempts=path.max_attempts,
        )

    @staticmethod
    def _open_attempt(attempts: list[AssessmentAttempt]) -> AssessmentAttempt | None:
        return next(
            (a for a in attempts if a.status in (*OPEN_ATTEMPTS, AttemptStatus.GRADING)), None
        )

    async def start_topic(
        self, user: CurrentUser, enrollment_id: int, step_id: int, assessment_type: str
    ) -> AttemptOutcome:
        """Intento del quiz con ítems no vistos; 202 si hay que generar más (U1b)."""
        if assessment_type != "topic":
            raise BusinessRuleError(
                "Only topic attempts are available on a step.", code="VALIDATION_ERROR"
            )
        enrollment, step = await self._own_step(user, enrollment_id, step_id, for_update=True)
        if is_closed(enrollment.status):
            raise path_errors.enrollment_closed()
        path = await self._path(enrollment)
        maximum = path.max_attempts + step.extra_attempts_granted
        if step.status == StepStatus.ATTEMPTS_EXHAUSTED:
            raise path_errors.max_attempts_exceeded(step.attempts_used, maximum)
        if (
            step.status not in (StepStatus.PENDING, StepStatus.IN_PROGRESS)
            or enrollment.status != EnrollmentStatus.IN_PATH
        ):
            raise path_errors.step_not_available(step.status)
        attempts = [
            a
            for a in await self._r.attempts.list_for_enrollment(enrollment_id)
            if a.path_step_id == step_id
        ]
        open_attempt = self._open_attempt(attempts)
        if open_attempt is not None:
            raise ConflictError(
                f"The attempt {open_attempt.id} is still open.", code="ATTEMPT_IN_PROGRESS"
            )
        if step.remaining_attempts(path.max_attempts) <= 0:
            raise path_errors.max_attempts_exceeded(step.attempts_used, maximum)
        seen = {i for a in attempts for i in (a.item_ids or [])}
        unseen = [
            i
            for i in await self._r.items.approved([step.topic_id], "topic_quiz")
            if i.id not in seen
        ]
        if len(unseen) < ITEMS_PER_ATTEMPT:
            job = await self._request_quiz_bank(enrollment, path, step.topic_id)
            if job.status != "succeeded" or not await self.ingest_quiz_bank_job(job):
                await self._uow.commit()
                return AttemptOutcome(job=JobRef(job.job_id, job.job_type, job.status))
            unseen = [
                i
                for i in await self._r.items.approved([step.topic_id], "topic_quiz")
                if i.id not in seen
            ]
            if not unseen:
                return AttemptOutcome(job=JobRef(job.job_id, job.job_type, job.status))
        picked = pick_quiz_items(unseen, ITEMS_PER_ATTEMPT)
        number = len(attempts) + 1
        if step.status == StepStatus.PENDING:
            await self._progress.set_step_status(step, StepStatus.IN_PROGRESS)
        attempt = await self._r.attempts.add(
            AssessmentAttempt(
                enrollment_id=enrollment_id,
                path_step_id=step_id,
                assessment_type="topic",
                attempt_number=number,
                item_ids=[require_id(i) for i in picked],
                uses_extra_grant=number > path.max_attempts,
            )
        )
        await self._uow.commit()
        return AttemptOutcome(view=AttemptView(attempt, picked, []))

    async def _request_final_bank(
        self, enrollment: Enrollment, path: LearningPath, topic_ids: list[int], upcoming: int
    ) -> JobStatus:
        """Pide a `ai/` una versión más de la final (B-011); la ingiere `ingest_final_bank`.

        La llave lleva el número de preguntas ya existentes: si cambian (por ejemplo, la IA
        devolvió solo preguntas descartadas), el pedido es otro trabajo y `ai/` no lo rechaza por
        reusar la llave con otra entrada.
        """
        stems: list[str] = []
        for topic_id in topic_ids:
            stems.extend(await self._r.items.stems_for_topic(topic_id, "final"))
        enrollment_id = require_id(enrollment)
        ref = await self._ai.submit_job(
            FINAL_BANK,
            {
                "learning_path_id": require_id(path),
                "topic_ids": [str(t) for t in topic_ids],
                "n_short_answer": FINAL_ON_DEMAND_SHORT_ANSWERS,
                "n_versions": 1,
                "previous_stems": stems[-200:],
            },
            f"{FINAL_BANK}:enrollment:{enrollment_id}:attempt:{upcoming}:v{len(stems)}",
            JobRefs(course_id=path.course_id, enrollment_id=enrollment_id),
        )
        return await self._ai.get_job(ref.job_id)

    async def _request_quiz_bank(
        self, enrollment: Enrollment, path: LearningPath, topic_id: int
    ) -> JobStatus:
        version = await self._r.items.count_for_topic(topic_id, "topic_quiz")
        ref = await self._ai.submit_job(
            QUIZ_BANK,
            {
                "topic_id": str(topic_id),
                "n_multiple_choice": ITEMS_PER_ATTEMPT - 1,
                "n_short_answer": 1,
                "previous_stems": (await self._r.items.stems_for_topic(topic_id, "topic_quiz"))[
                    -200:
                ],
            },
            f"{QUIZ_BANK}:topic:{topic_id}:v{version}",
            JobRefs(
                course_id=path.course_id, topic_id=topic_id, enrollment_id=require_id(enrollment)
            ),
        )
        return await self._ai.get_job(ref.job_id)

    async def start_final(self, user: CurrentUser, enrollment_id: int) -> AttemptOutcome:
        """Intento de la evaluación final: solo con todos los pasos `passed` o `skipped` (E8)."""
        enrollment = await self._own_enrollment(user, enrollment_id, for_update=True)
        if is_closed(enrollment.status):
            raise path_errors.enrollment_closed()
        if enrollment.status != EnrollmentStatus.FINAL_READY:
            raise BusinessRuleError(
                "The final assessment needs every step passed or skipped.",
                code="FINAL_ASSESSMENT_LOCKED",
            )
        path = await self._path(enrollment)
        attempts = [
            a
            for a in await self._r.attempts.list_for_enrollment(enrollment_id)
            if a.assessment_type == "final"
        ]
        open_attempt = self._open_attempt(attempts)
        if open_attempt is not None:
            raise ConflictError(
                f"The attempt {open_attempt.id} is still open.", code="ATTEMPT_IN_PROGRESS"
            )
        used, maximum = await self._final_counters(enrollment, path)
        if used >= maximum:
            raise path_errors.max_attempts_exceeded(used, maximum)
        steps = await self._r.steps.list_for_enrollment(enrollment_id)
        topic_order = [s.topic_id for s in steps]
        seen = {i for a in attempts for i in (a.item_ids or [])}
        unseen = [i for i in await self._r.items.approved(topic_order, "final") if i.id not in seen]
        # B-011: al publicar se generan pocas preguntas de la final (unas 3 por tema), así que un
        # reintento se quedaba sin preguntas no vistas. Como en el quiz (ADR 0015, U1b), se piden
        # más bajo demanda: en un reintento con menos de FINAL_ITEMS sin ver, o si no queda
        # ninguna. Las generadas llevan en `auto_review` para qué intento se pidieron: si ya hay,
        # no se pide otra vez (a lo sumo una generación por intento, sin ciclos).
        upcoming = len(attempts) + 1
        already = any(_generated_for(i, enrollment_id, upcoming) for i in unseen)
        if not already and (not unseen or (attempts and len(unseen) < FINAL_ITEMS)):
            job = await self._request_final_bank(enrollment, path, topic_order, upcoming)
            if not job.is_finished:
                await self._uow.commit()
                return AttemptOutcome(job=JobRef(job.job_id, job.job_type, job.status))
            if job.status == "succeeded":
                await self.ingest_final_bank_job(job)
            unseen = [
                i for i in await self._r.items.approved(topic_order, "final") if i.id not in seen
            ]
        picked = round_robin(unseen, topic_order, FINAL_ITEMS)
        if not picked:
            raise ConflictError("There are no unseen approved final items for this path.")
        number = len(attempts) + 1
        attempt = await self._r.attempts.add(
            AssessmentAttempt(
                enrollment_id=enrollment_id,
                assessment_type="final",
                attempt_number=number,
                item_ids=[require_id(i) for i in picked],
                uses_extra_grant=number > path.max_attempts,
            )
        )
        await self._uow.commit()
        return AttemptOutcome(view=AttemptView(attempt, picked, []))

    async def _own_attempt(
        self, user: CurrentUser, attempt_id: int, *, for_update: bool = False
    ) -> tuple[AssessmentAttempt, Enrollment]:
        attempt = await self._r.attempts.get(attempt_id, for_update=for_update)
        enrollment = await self._r.enrollments.get(attempt.enrollment_id) if attempt else None
        if (
            attempt is None
            or not attempt.active
            or enrollment is None
            or enrollment.user_id != user.id
        ):
            raise NotFoundError("Attempt", attempt_id, code="ATTEMPT_NOT_FOUND")
        return attempt, enrollment

    async def _view(self, attempt: AssessmentAttempt) -> AttemptView:
        items = await self._r.items.by_ids(list(attempt.item_ids or []))
        answers = await self._r.answers.list_for_attempt(require_id(attempt))
        return AttemptView(
            attempt, [items[i] for i in attempt.item_ids or [] if i in items], answers
        )

    async def get(self, user: CurrentUser, attempt_id: int) -> AttemptView:
        attempt, _ = await self._own_attempt(user, attempt_id)
        return await self._view(attempt)

    async def save_answers(
        self, user: CurrentUser, attempt_id: int, answers: list[LearnerAnswerInput]
    ) -> int:
        attempt, _ = await self._own_attempt(user, attempt_id, for_update=True)
        if attempt.status not in OPEN_ATTEMPTS:
            raise ConflictError(
                "The attempt was already submitted.", code="ATTEMPT_ALREADY_SUBMITTED"
            )
        _check_items(answers, set(attempt.item_ids or []))
        existing = {
            a.assessment_item_id: a for a in await self._r.answers.list_for_attempt(attempt_id)
        }
        for answer in answers:
            values = {
                "selected_option": None
                if answer.selected_option is None
                else str(answer.selected_option),
                "dont_know": answer.dont_know,
                "text_answer": answer.text_answer,
            }
            current = existing.get(answer.item_id)
            if current is None:
                await self._r.answers.add(
                    AttemptAnswer(
                        assessment_attempt_id=attempt_id,
                        assessment_item_id=answer.item_id,
                        selected_option=(
                            None if answer.selected_option is None else str(answer.selected_option)
                        ),
                        dont_know=answer.dont_know,
                        text_answer=answer.text_answer,
                    )
                )
            else:
                await self._r.answers.update(require_id(current), values)
        if attempt.status == AttemptStatus.CREATED:
            check_attempt_transition(attempt.status, AttemptStatus.IN_PROGRESS)
            await self._r.attempts.update(attempt_id, {"status": AttemptStatus.IN_PROGRESS})
        await self._uow.commit()
        return len(answers)

    async def submit(self, user: CurrentUser, attempt_id: int) -> AttemptOutcome:
        """Opción múltiple por regla (200); con respuesta corta, `grading.short_answer` (202)."""
        attempt, enrollment = await self._own_attempt(user, attempt_id, for_update=True)
        if attempt.status not in OPEN_ATTEMPTS:
            raise ConflictError(
                "The attempt was already submitted.", code="ATTEMPT_ALREADY_SUBMITTED"
            )
        enrollment = await self._r.enrollments.get_for_update(require_id(enrollment)) or enrollment
        if is_closed(enrollment.status):
            raise path_errors.enrollment_closed()
        path = await self._path(enrollment)
        items = await self._r.items.by_ids(list(attempt.item_ids or []))
        existing = {
            a.assessment_item_id: a for a in await self._r.answers.list_for_attempt(attempt_id)
        }
        for item_id in attempt.item_ids or []:
            if item_id not in existing:
                existing[item_id] = await self._r.answers.add(
                    AttemptAnswer(assessment_attempt_id=attempt_id, assessment_item_id=item_id)
                )
        status = attempt.status
        for target in (AttemptStatus.IN_PROGRESS, AttemptStatus.SUBMITTED, AttemptStatus.GRADING):
            if status == target:
                continue
            check_attempt_transition(status, target)
            status = target
        await self._r.attempts.update(attempt_id, {"status": status, "submitted_at": _now()})
        if attempt.path_step_id is not None:
            step = await self._r.steps.get(attempt.path_step_id)
            if step is not None:  # el intento cuenta en cuanto se envía
                await self._r.steps.update(
                    require_id(step), {"attempts_used": step.attempts_used + 1}
                )
        jobs: list[JobRef] = []
        ratio = _short_answer_ratio(path)
        for item_id, answer in existing.items():
            item = items.get(item_id)
            if item is None:
                continue
            if item.item_type == SHORT_ANSWER:
                jobs.append(
                    await self._jobs.grading_job(answer, item, ratio, require_id(enrollment))
                )
                continue
            grading = grade_multiple_choice(item, answer)
            await self._r.answers.update(
                require_id(answer),
                {
                    "is_correct": grading["is_correct"],
                    "score": grading["score"],
                    "grader": "rule",
                    "rubric_detail": grading,
                    "feedback": None,
                },
            )
        if jobs:
            await self._uow.commit()
            return AttemptOutcome(job=jobs[0])
        graded = await self._finalize(require_id(attempt), enrollment, path)
        await self._uow.commit()
        return AttemptOutcome(result=await self._result_view(graded, path))

    async def _finalize(
        self, attempt_id: int, enrollment: Enrollment, path: LearningPath
    ) -> AssessmentAttempt:
        """Cierra un intento calificado y aplica sus efectos en el paso, la final y el badge."""
        attempt = await self._r.attempts.get(attempt_id)
        assert attempt is not None  # noqa: S101
        answers = await self._r.answers.list_for_attempt(attempt_id)
        score = attempt_score(a.score for a in answers)
        is_final = attempt.assessment_type == "final"
        threshold = path.final_pass_threshold if is_final else path.topic_pass_threshold
        passed = score >= threshold
        check_attempt_transition(attempt.status, AttemptStatus.GRADED)
        graded = await self._r.attempts.update(
            attempt_id,
            {"status": AttemptStatus.GRADED, "score": score, "passed": passed, "graded_at": _now()},
        )
        assert graded is not None  # noqa: S101
        if not is_final and attempt.path_step_id is not None:
            step = await self._r.steps.get(attempt.path_step_id)
            if step is not None:
                await self._progress.apply_topic_result(
                    enrollment, path, step, score=score, passed=passed
                )
        elif is_final:
            if passed:
                completed = await self._progress.set_enrollment_status(
                    enrollment, EnrollmentStatus.COMPLETED, completed_at=_now()
                )
                await self._issue_badge(completed, path, score)
            else:
                used, maximum = await self._final_counters(enrollment, path)
                if used >= maximum:
                    await self._progress.alert(path, AlertType.FINAL_ATTEMPTS_EXHAUSTED, enrollment)
        return graded

    async def _issue_badge(self, enrollment: Enrollment, path: LearningPath, score: float) -> Badge:
        """El badge solo se emite con la final aprobada (y una vez por inscripción)."""
        existing = await self._r.badges.by_enrollment(require_id(enrollment))
        if existing is not None:
            return existing
        learner = await self._r.reader.user(enrollment.user_id)
        course = await self._course(path)
        nodes = await self._r.reader.topic_nodes(path.course_id)
        public_id = uuid4()
        objective = " ".join(
            p
            for p in (
                enrollment.objective_bloom_verb,
                enrollment.objective_content,
                enrollment.objective_criterion,
            )
            if p
        )
        settings = get_settings()
        assertion = badges.build_assertion(
            public_id=public_id,
            base_url="",
            email=learner.email if learner is not None else str(public_id),
            issued_on=_now().replace(microsecond=0),
            course_name=course.name,
            path_name=path.name,
            objective=objective or None,
            topic_names=[n.name for n in nodes],
            final_score=score,
            final_pass_threshold=path.final_pass_threshold,
            issuer_name=settings.badge_issuer_name or "SmartMentor",
            issuer_url=settings.badge_issuer_url or "http://localhost:8501",
        )
        return await self._r.badges.add(
            Badge(
                enrollment_id=require_id(enrollment),
                public_id=public_id,
                image_path=f"badges/{public_id}.png",
                image_url=badges.IMAGE_PATH.format(public_id=public_id),
                open_badges_metadata=assertion,
            )
        )

    async def _result_view(
        self, attempt: AssessmentAttempt, path: LearningPath
    ) -> AttemptResultView:
        enrollment = await self._r.enrollments.get(attempt.enrollment_id)
        assert enrollment is not None  # noqa: S101
        answers = await self._r.answers.list_for_attempt(require_id(attempt))
        items = await self._r.items.by_ids([a.assessment_item_id for a in answers])
        if attempt.assessment_type == "final":
            used, maximum = await self._final_counters(enrollment, path)
            threshold = path.final_pass_threshold
            remedial = None
        else:
            step = await self._r.steps.get(attempt.path_step_id or 0)
            used = step.attempts_used if step else 0
            maximum = path.max_attempts + (step.extra_attempts_granted if step else 0)
            threshold = path.topic_pass_threshold
            remedial = (
                await self._r.content.remedial_resource_id(step.topic_id, require_id(enrollment))
                if step is not None and not attempt.passed
                else None
            )
        progress = LearnerProgress(self._r, self._ai, self._uow)
        return AttemptResultView(
            attempt=attempt,
            pass_threshold=threshold,
            answers=[(a, items.get(a.assessment_item_id)) for a in answers],
            attempts_used=used,
            attempts_max=maximum,
            remedial_resource_id=remedial,
            next_action=await progress.next_action_of(enrollment),
        )

    async def result(self, user: CurrentUser, attempt_id: int) -> AttemptResultView:
        attempt, enrollment = await self._own_attempt(user, attempt_id)
        path = await self._path(enrollment)
        if attempt.status != AttemptStatus.GRADED:
            extra: dict[str, Any] = {}
            if attempt.status == AttemptStatus.GRADING:
                job = await LearnerProgress(self._r, self._ai, self._uow)._first_grading_job(
                    attempt, enrollment, path
                )
                if job:
                    extra["job_id"] = job
            raise ConflictError(
                "The attempt is not graded yet.", code="ATTEMPT_NOT_GRADED", extra=extra
            )
        return await self._result_view(attempt, path)

    async def request_review(self, user: CurrentUser, answer_id: int) -> int | None:
        """Pide la revisión humana de una respuesta corta calificada por el LLM (E7, CU-19)."""
        answer = await self._r.answers.get(answer_id)
        attempt = await self._r.attempts.get(answer.assessment_attempt_id) if answer else None
        enrollment = await self._r.enrollments.get(attempt.enrollment_id) if attempt else None
        if answer is None or attempt is None or enrollment is None or enrollment.user_id != user.id:
            raise NotFoundError("Attempt answer", answer_id)
        if answer.grader != "llm_judge" or attempt.status != AttemptStatus.GRADED:
            raise BusinessRuleError(
                "Only short answers graded by the LLM can be reviewed.", code="REVIEW_NOT_ALLOWED"
            )
        if answer.review_requested_at is not None:
            raise ConflictError(
                "The review was already requested.", code="REVIEW_ALREADY_REQUESTED"
            )
        await self._r.answers.update(answer_id, {"review_requested_at": _now()})
        path = await self._path(enrollment)
        alert = await self._progress.alert(
            path, AlertType.REVIEW_REQUESTED, enrollment, attempt.path_step_id
        )
        await self._uow.commit()
        return alert.id if alert is not None else None

    async def review_plan(self, user: CurrentUser, enrollment_id: int) -> list[WeakTopic]:
        """Temas débiles del último intento final (E9)."""
        enrollment = await self._own_enrollment(user, enrollment_id)
        path = await self._path(enrollment)
        finals = [
            a
            for a in await self._r.attempts.list_for_enrollment(enrollment_id)
            if a.assessment_type == "final" and a.status == AttemptStatus.GRADED
        ]
        if not finals:
            return []
        answers = await self._r.answers.list_for_attempt(require_id(finals[-1]))
        items = await self._r.items.by_ids([a.assessment_item_id for a in answers])
        scores: dict[int, list[float]] = defaultdict(list)
        for answer in answers:
            item = items.get(answer.assessment_item_id)
            if item is not None:
                scores[item.topic_id].append(answer.score or 0.0)
        names = {n.id: n.name for n in await self._r.reader.topic_nodes(path.course_id)}
        weak: list[WeakTopic] = []
        for topic_id, values in scores.items():
            average = round(sum(values) / len(values), 2)
            if average < path.topic_pass_threshold:
                explanation = await self._r.content.explanation(topic_id)
                weak.append(
                    WeakTopic(
                        topic_id=topic_id,
                        name=names.get(topic_id, ""),
                        score=average,
                        resource_id=explanation["resource_id"] if explanation else None,
                    )
                )
        return sorted(weak, key=lambda w: w.score)

    async def history(
        self, user: CurrentUser, enrollment_id: int, step_id: int | None
    ) -> list[AttemptHistoryEntry]:
        """Intentos calificados de un tema o de la final, para el historial (E7c, E9c)."""
        enrollment = await self._own_enrollment(user, enrollment_id)
        if step_id is not None:
            step = await self._r.steps.get(step_id)
            if step is None or step.enrollment_id != enrollment_id:
                raise path_errors.step_not_found(step_id)
        kind = "topic" if step_id is not None else "final"
        entries: list[AttemptHistoryEntry] = []
        for attempt in await self._r.attempts.list_for_enrollment(require_id(enrollment)):
            if (
                attempt.assessment_type != kind
                or attempt.path_step_id != step_id
                or attempt.status != AttemptStatus.GRADED
            ):
                continue
            answers = await self._r.answers.list_for_attempt(require_id(attempt))
            entries.append(
                AttemptHistoryEntry(
                    attempt_id=require_id(attempt),
                    number=attempt.attempt_number,
                    score=attempt.score or 0.0,
                    correct=sum(1 for a in answers if a.is_correct),
                    total=len(answers),
                    extra_grant=attempt.uses_extra_grant,
                    passed=bool(attempt.passed),
                )
            )
        return entries

    async def final_counters(self, user: CurrentUser, enrollment_id: int) -> tuple[int, int]:
        enrollment = await self._own_enrollment(user, enrollment_id)
        return await self._final_counters(enrollment, await self._path(enrollment))

    # --- ingesta de `grading.short_answer` --------------------------------------------------

    async def _apply_grading(self, answer: AttemptAnswer, result: GradingV1, ratio: float) -> None:
        correct = short_answer_is_correct(result.criteria_met, result.criteria_total, ratio)
        detail = result.model_dump(mode="json", exclude={"meta"}) | {
            "is_correct": correct,
            "min_criteria_ratio": round(ratio, 4),
        }
        await self._r.answers.update(
            require_id(answer),
            {
                "is_correct": correct,
                "score": result.score,
                "grader": "llm_judge",
                "rubric_detail": detail,
                "feedback": result.feedback,
            },
        )

    async def ingest_grading(self, job: JobStatus, result: BaseModel) -> bool:
        assert isinstance(result, GradingV1)  # noqa: S101
        enrollment_id = job.refs.enrollment_id
        enrollment = (
            await self._r.enrollments.get_for_update(enrollment_id) if enrollment_id else None
        )
        if enrollment is None or not result.item_id.isdigit():
            await self._uow.commit()
            return False
        path = await self._path(enrollment)
        ratio = _short_answer_ratio(path)
        for attempt in await self._r.attempts.list_for_enrollment(require_id(enrollment)):
            if attempt.status != AttemptStatus.GRADING:
                continue
            attempt = await self._r.attempts.get(require_id(attempt), for_update=True) or attempt
            answers = await self._r.answers.list_for_attempt(require_id(attempt))
            items = await self._r.items.by_ids([a.assessment_item_id for a in answers])
            target = next(
                (
                    a
                    for a in answers
                    if a.assessment_item_id == int(result.item_id) and a.grader is None
                ),
                None,
            )
            if target is None:
                continue
            item = items[target.assessment_item_id]
            current = await self._jobs.grading_job(target, item, ratio, require_id(enrollment))
            if current.job_id != job.job_id:
                continue
            await self._apply_grading(target, result, ratio)
            # Las demás respuestas cortas del intento: se ingieren si su trabajo ya terminó.
            pending = 0
            for other in answers:
                other_item = items.get(other.assessment_item_id)
                if other is target or other.grader is not None or other_item is None:
                    continue
                if other_item.item_type != SHORT_ANSWER:
                    continue
                ref = await self._jobs.grading_job(other, other_item, ratio, require_id(enrollment))
                status = await self._ai.get_job(ref.job_id)
                if status.status == "succeeded":
                    try:
                        await self._apply_grading(
                            other, GradingV1.model_validate(status.result), ratio
                        )
                        continue
                    except ValidationError:
                        logger.error("invalid grading result", extra={"job_id": ref.job_id})
                pending += 1
            if pending == 0:
                await self._finalize(require_id(attempt), enrollment, path)
            await self._uow.commit()
            return True
        await self._uow.commit()
        return False

    async def grading_failed(self, job: JobStatus) -> None:
        enrollment_id = job.refs.enrollment_id
        if enrollment_id is not None:
            for attempt in await self._r.attempts.list_for_enrollment(enrollment_id):
                if attempt.status == AttemptStatus.GRADING:
                    check_attempt_transition(attempt.status, AttemptStatus.GRADING_FAILED)
                    await self._r.attempts.update(
                        require_id(attempt), {"status": AttemptStatus.GRADING_FAILED}
                    )
        await self._uow.commit()

    async def pending_gradings(self) -> list[PendingJob]:
        pending: list[PendingJob] = []
        for attempt in await self._r.attempts.list_by_status(AttemptStatus.GRADING):
            enrollment = await self._r.enrollments.get(attempt.enrollment_id)
            if enrollment is None:
                continue
            path = await self._path(enrollment)
            job_id = await LearnerProgress(self._r, self._ai, self._uow)._first_grading_job(
                attempt, enrollment, path
            )
            if job_id and (await self._ai.get_job(job_id)).is_finished:
                pending.append(PendingJob(job_id=job_id, job_type=GRADING_SHORT_ANSWER))
        return pending

    # --- ingesta del banco del quiz bajo demanda (U1b) ----------------------------------------

    async def ingest_quiz_bank_job(self, job: JobStatus) -> bool:
        try:
            parsed = AssessmentItemBankV1.model_validate(job.result)
        except ValidationError as exc:
            raise AiResultInvalidError(job.job_id) from exc
        return await self.ingest_quiz_bank(job, parsed)

    async def ingest_quiz_bank(self, job: JobStatus, result: BaseModel) -> bool:
        """Guarda los ítems generados bajo demanda.

        Decisión: como el aprendiz espera (U1b), los ítems que pasaron la revisión automática
        entran `approved` (marcados `on_demand` en `auto_review` para que el instructor los revise
        y los retire si hace falta); los descartados quedan `auto_rejected`.
        """
        assert isinstance(result, AssessmentItemBankV1)  # noqa: S101
        await self._r.items.lock_job(job.job_id)
        if await self._r.items.exists_for_job(job.job_id):
            return False
        topic_id = job.refs.topic_id or (
            int(result.topic_id) if result.topic_id and result.topic_id.isdigit() else None
        )
        if topic_id is None:
            raise AiResultInvalidError(job.job_id)
        outcomes = {o["id"] for o in await self._r.content.outcomes(topic_id)}
        reviews = {r.item_id: r.model_dump() for r in result.item_reviews}
        discarded = set(result.discarded_item_ids)
        for item in result.items:
            outcome = int(item.outcome_id) if item.outcome_id.isdigit() else None
            await self._r.items.add(
                AssessmentItem(
                    topic_id=topic_id,
                    learning_outcome_id=outcome if outcome in outcomes else None,
                    source="topic_quiz",
                    item_type=item.item_type,
                    bloom_level=item.bloom_level,
                    difficulty=item.difficulty,
                    stem=item.stem,
                    options=item.options or None,
                    correct_option=None
                    if item.correct_option is None
                    else str(item.correct_option),
                    model_answer=item.model_answer or None,
                    rubric=[c.model_dump() for c in item.rubric] or None,
                    equivalence_group=item.equivalence_group,
                    review_status="auto_rejected" if item.id in discarded else "approved",
                    auto_review={
                        "job_id": job.job_id,
                        "on_demand": True,
                        "review": reviews.get(item.id),
                    },
                    prompt_version=result.meta.prompt_version,
                )
            )
        await self._uow.commit()
        return True

    # --- ingesta del banco de la final bajo demanda (B-011) --------------------------------------

    async def ingest_final_bank_job(self, job: JobStatus) -> bool:
        try:
            parsed = AssessmentItemBankV1.model_validate(job.result)
        except ValidationError as exc:
            raise AiResultInvalidError(job.job_id) from exc
        return await self.ingest_final_bank(job, parsed)

    async def ingest_final_bank(self, job: JobStatus, result: BaseModel) -> bool:
        """Guarda las preguntas de la final generadas bajo demanda para un reintento.

        Misma decisión que en el quiz (`ingest_quiz_bank`): el aprendiz espera (U1d), así que las
        que pasaron la revisión automática entran `approved`, marcadas `on_demand` para que el
        instructor las revise. Solo se guardan las de temas de la ruta de la inscripción; con
        `n_versions=1` todas son `final`.
        """
        assert isinstance(result, AssessmentItemBankV1)  # noqa: S101
        await self._r.items.lock_job(job.job_id)
        if await self._r.items.exists_for_job(job.job_id):
            return False
        enrollment_id = job.refs.enrollment_id
        if enrollment_id is None:
            raise AiResultInvalidError(job.job_id)
        steps = await self._r.steps.list_for_enrollment(enrollment_id)
        path_topics = {s.topic_id for s in steps}
        # Aún no existe el intento para el que se pidieron (se crea con estas preguntas).
        upcoming = 1 + sum(
            1
            for a in await self._r.attempts.list_for_enrollment(enrollment_id)
            if a.assessment_type == "final"
        )
        reviews = {r.item_id: r.model_dump() for r in result.item_reviews}
        discarded = set(result.discarded_item_ids)
        outcomes: dict[int, set[int]] = {}
        for item in result.items:
            topic_id = int(item.topic_id) if item.topic_id.isdigit() else None
            if topic_id is None or topic_id not in path_topics:
                continue
            if topic_id not in outcomes:
                outcomes[topic_id] = {o["id"] for o in await self._r.content.outcomes(topic_id)}
            outcome = int(item.outcome_id) if item.outcome_id.isdigit() else None
            await self._r.items.add(
                AssessmentItem(
                    topic_id=topic_id,
                    learning_outcome_id=outcome if outcome in outcomes[topic_id] else None,
                    source=item.source,
                    item_type=item.item_type,
                    bloom_level=item.bloom_level,
                    difficulty=item.difficulty,
                    stem=item.stem,
                    options=item.options or None,
                    correct_option=None
                    if item.correct_option is None
                    else str(item.correct_option),
                    model_answer=item.model_answer or None,
                    rubric=[c.model_dump() for c in item.rubric] or None,
                    equivalence_group=item.equivalence_group,
                    review_status="auto_rejected" if item.id in discarded else "approved",
                    auto_review={
                        "job_id": job.job_id,
                        "on_demand": True,
                        "enrollment_id": enrollment_id,
                        "final_attempt": upcoming,
                        "review": reviews.get(item.id),
                    },
                    prompt_version=result.meta.prompt_version,
                )
            )
        await self._uow.commit()
        return True


def _generated_for(item: AssessmentItem, enrollment_id: int, attempt: int) -> bool:
    """Si la pregunta se generó bajo demanda para ese intento de la final (B-011)."""
    review = item.auto_review or {}
    return (
        bool(review.get("on_demand"))
        and review.get("enrollment_id") == enrollment_id
        and review.get("final_attempt") == attempt
    )


class BadgeService(_Base):
    async def _views(self, enrollments: list[Enrollment]) -> list[BadgeView]:
        by_id = {require_id(e): e for e in enrollments}
        views: list[BadgeView] = []
        for badge in await self._r.badges.for_enrollments(list(by_id)):
            enrollment = by_id[badge.enrollment_id]
            path = await self._path(enrollment)
            views.append(BadgeView(badge, enrollment, path, await self._course(path)))
        return views

    async def mine(self, user: CurrentUser) -> list[BadgeView]:
        enrollments, _ = await self._r.enrollments.list_for_user(user.id, limit=1000, offset=0)
        return await self._views(enrollments)

    async def for_enrollment(self, user: CurrentUser, enrollment_id: int) -> BadgeView:
        enrollment = await self._own_enrollment(user, enrollment_id)
        views = await self._views([enrollment])
        if not views:
            raise NotFoundError("Badge", enrollment_id, code="BADGE_NOT_FOUND")
        return views[0]

    async def public(self, public_id: UUID) -> Badge:
        badge = await self._r.badges.by_public_id(public_id)
        if badge is None or not badge.open_badges_metadata:
            raise NotFoundError("Badge", str(public_id), code="BADGE_NOT_FOUND")
        return badge
