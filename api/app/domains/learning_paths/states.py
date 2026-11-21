"""Máquinas de estados de la inscripción, el paso y el intento (plan 5.1, design/01/estados.md).

Funciones puras: no tocan la base ni FastAPI. La API decide los estados y la app navega con
`next_action` (nunca los deduce, plan 5.5).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.common.exceptions import InvalidStateTransitionError


class EnrollmentStatus(StrEnum):
    ENROLLED = "enrolled"
    PROFILING = "profiling"
    DIAGNOSING = "diagnosing"
    OBJECTIVE_PENDING = "objective_pending"
    IN_PATH = "in_path"
    FINAL_READY = "final_ready"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    WITHDRAWN = "withdrawn"


class StepStatus(StrEnum):
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    ATTEMPTS_EXHAUSTED = "attempts_exhausted"
    ON_HOLD = "on_hold"


class AttemptStatus(StrEnum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    GRADING = "grading"
    GRADED = "graded"
    GRADING_FAILED = "grading_failed"


class InclusionReason(StrEnum):
    SKIPPED_MASTERED = "skipped_mastered"
    WEAK_PREREQUISITE = "weak_prerequisite"
    OBJECTIVE_FOCUS = "objective_focus"
    REQUIRED_BY_PATH = "required_by_path"
    MANDATORY = "mandatory"
    FIXED_PATH = "fixed_path"


class AlertType(StrEnum):
    TOPIC_ATTEMPTS_EXHAUSTED = "topic_attempts_exhausted"
    FINAL_ATTEMPTS_EXHAUSTED = "final_attempts_exhausted"
    REVIEW_REQUESTED = "review_requested"


CLOSED_ENROLLMENT = frozenset(
    {EnrollmentStatus.COMPLETED, EnrollmentStatus.ABANDONED, EnrollmentStatus.WITHDRAWN}
)
_OPEN_ENROLLMENT = [s for s in EnrollmentStatus if s not in CLOSED_ENROLLMENT]

ENROLLMENT_TRANSITIONS: dict[str, frozenset[str]] = {
    EnrollmentStatus.ENROLLED: frozenset({"profiling", "diagnosing"}),
    EnrollmentStatus.PROFILING: frozenset({"diagnosing"}),
    EnrollmentStatus.DIAGNOSING: frozenset({"objective_pending"}),
    EnrollmentStatus.OBJECTIVE_PENDING: frozenset({"in_path"}),
    EnrollmentStatus.IN_PATH: frozenset({"final_ready"}),
    # final no aprobada con intentos: sigue en final_ready (repaso y nuevo intento)
    EnrollmentStatus.FINAL_READY: frozenset({"completed", "final_ready"}),
    EnrollmentStatus.COMPLETED: frozenset(),
    EnrollmentStatus.ABANDONED: frozenset(),
    EnrollmentStatus.WITHDRAWN: frozenset(),
}
# Desde cualquier estado no final: abandonar (aprendiz) o retirar (admin).
for _status in _OPEN_ENROLLMENT:
    ENROLLMENT_TRANSITIONS[_status] = ENROLLMENT_TRANSITIONS[_status] | {"abandoned", "withdrawn"}

STEP_TRANSITIONS: dict[str, frozenset[str]] = {
    StepStatus.BLOCKED: frozenset({"pending", "on_hold"}),
    StepStatus.PENDING: frozenset({"in_progress", "on_hold", "blocked"}),
    StepStatus.IN_PROGRESS: frozenset({"passed", "in_progress", "attempts_exhausted"}),
    StepStatus.ATTEMPTS_EXHAUSTED: frozenset({"in_progress"}),
    StepStatus.ON_HOLD: frozenset({"pending", "blocked"}),
    StepStatus.PASSED: frozenset(),
    StepStatus.SKIPPED: frozenset(),
}
# Recalcular la ruta (E15, cambio de perfil) solo toca pasos que no se han empezado.
RESEQUENCEABLE_STEPS = frozenset(
    {StepStatus.SKIPPED, StepStatus.BLOCKED, StepStatus.PENDING, StepStatus.ON_HOLD}
)

ATTEMPT_TRANSITIONS: dict[str, frozenset[str]] = {
    AttemptStatus.CREATED: frozenset({"in_progress"}),
    AttemptStatus.IN_PROGRESS: frozenset({"in_progress", "submitted"}),
    AttemptStatus.SUBMITTED: frozenset({"grading"}),
    AttemptStatus.GRADING: frozenset({"graded", "grading_failed"}),
    AttemptStatus.GRADING_FAILED: frozenset({"grading"}),
    AttemptStatus.GRADED: frozenset(),
}

DONE_STEPS = frozenset({StepStatus.PASSED, StepStatus.SKIPPED})
OPEN_ATTEMPTS = frozenset({AttemptStatus.CREATED, AttemptStatus.IN_PROGRESS})


def _check(table: Mapping[str, frozenset[str]], entity: str, current: str, target: str) -> None:
    if target not in table.get(current, frozenset()):
        raise InvalidStateTransitionError(f"The {entity} cannot go from '{current}' to '{target}'.")


def check_enrollment_transition(current: str, target: str) -> None:
    _check(ENROLLMENT_TRANSITIONS, "enrollment", current, target)


def check_step_transition(current: str, target: str) -> None:
    _check(STEP_TRANSITIONS, "path step", current, target)


def check_attempt_transition(current: str, target: str) -> None:
    _check(ATTEMPT_TRANSITIONS, "attempt", current, target)


def is_closed(status: str) -> bool:
    return status in CLOSED_ENROLLMENT


# --- disponibilidad de los pasos (avance no lineal) -------------------------------------------


@dataclass(frozen=True)
class StepState:
    step_id: int
    topic_id: int
    step_order: int
    status: str


def refresh_availability(
    steps: Iterable[StepState], prerequisites: Mapping[int, Iterable[int]]
) -> dict[int, str]:
    """Nuevo estado de los pasos que esperan (`blocked`, `pending`, `on_hold`).

    - `on_hold` si algún prerrequisito está `attempts_exhausted` u `on_hold` (los dependientes de
      un tema agotado esperan; los demás siguen disponibles).
    - `pending` si todos sus prerrequisitos están `passed` o `skipped`.
    - `blocked` en otro caso.
    Devuelve solo los pasos cuyo estado cambia: `{step_id: nuevo_estado}`.
    """
    ordered = sorted(steps, key=lambda s: s.step_order)
    status_by_topic = {s.topic_id: s.status for s in ordered}
    changes: dict[int, str] = {}
    # Dos pasadas bastan en un DAG ordenado topológicamente; se itera hasta estabilizar.
    for _ in range(len(ordered) + 1):
        moved = False
        for step in ordered:
            current = status_by_topic[step.topic_id]
            if current not in (StepStatus.BLOCKED, StepStatus.PENDING, StepStatus.ON_HOLD):
                continue
            pre = [
                status_by_topic[p]
                for p in prerequisites.get(step.topic_id, ())
                if p in status_by_topic
            ]
            if any(p in (StepStatus.ATTEMPTS_EXHAUSTED, StepStatus.ON_HOLD) for p in pre):
                target = StepStatus.ON_HOLD
            elif all(p in DONE_STEPS for p in pre):
                target = StepStatus.PENDING
            else:
                target = StepStatus.BLOCKED
            if target != current:
                status_by_topic[step.topic_id] = target
                changes[step.step_id] = target
                moved = True
        if not moved:
            break
    original = {s.step_id: s.status for s in ordered}
    return {k: v for k, v in changes.items() if original[k] != v}


def all_steps_done(statuses: Iterable[str]) -> bool:
    return all(s in DONE_STEPS for s in statuses)


# --- next_action ------------------------------------------------------------------------------


@dataclass(frozen=True)
class NextAction:
    type: str
    screen: str
    step_id: int | None = None
    attempt_id: int | None = None
    job_id: str | None = None


@dataclass(frozen=True)
class ProgressFacts:
    """Lo que hace falta saber de una inscripción para decidir la siguiente acción."""

    status: str
    diagnostic_status: str | None = None
    diagnostic_job_id: str | None = None
    steps: tuple[StepState, ...] = ()
    open_attempt_id: int | None = None
    open_attempt_step_id: int | None = None
    grading_attempt_id: int | None = None
    grading_job_id: str | None = None
    last_final_attempt_id: int | None = None
    last_final_passed: bool | None = None
    final_attempts_remaining: int = 0
    has_survey: bool = False


def next_action(facts: ProgressFacts) -> NextAction:
    """La siguiente acción del aprendiz (docs/contracts/api-v2.md, sección 3.2)."""
    status = facts.status
    if status in (EnrollmentStatus.ABANDONED, EnrollmentStatus.WITHDRAWN):
        return NextAction("none", "E11")
    if status in (EnrollmentStatus.ENROLLED, EnrollmentStatus.PROFILING):
        return NextAction("complete_profile", "E2")
    if status == EnrollmentStatus.DIAGNOSING:
        if facts.diagnostic_status is None:
            return NextAction("start_diagnostic", "E3")
        if facts.diagnostic_status in ("submitted", "scoring") and facts.diagnostic_job_id:
            return NextAction("wait_job", "U1a", job_id=facts.diagnostic_job_id)
        return NextAction("continue_diagnostic", "E3")
    if status == EnrollmentStatus.OBJECTIVE_PENDING:
        return NextAction("confirm_objective", "E4")
    if status == EnrollmentStatus.COMPLETED:
        if not facts.has_survey:
            return NextAction("answer_survey", "E13a")
        return NextAction("view_badge", "E10")
    # in_path y final_ready: primero lo que está abierto o calificándose
    if facts.open_attempt_id is not None:
        screen = "E6b" if facts.open_attempt_step_id is not None else "E8"
        return NextAction(
            "continue_attempt",
            screen,
            step_id=facts.open_attempt_step_id,
            attempt_id=facts.open_attempt_id,
        )
    if facts.grading_attempt_id is not None and facts.grading_job_id:
        return NextAction(
            "wait_job", "U1c", attempt_id=facts.grading_attempt_id, job_id=facts.grading_job_id
        )
    if status == EnrollmentStatus.IN_PATH:
        ordered = sorted(facts.steps, key=lambda s: s.step_order)
        for step in ordered:
            if step.status in (StepStatus.IN_PROGRESS, StepStatus.PENDING):
                return NextAction("study_topic", "E6", step_id=step.step_id)
        for step in ordered:
            if step.status in (StepStatus.ATTEMPTS_EXHAUSTED, StepStatus.ON_HOLD):
                return NextAction("wait_instructor", "E7c", step_id=step.step_id)
        return NextAction("none", "E11")
    # final_ready
    if facts.last_final_attempt_id is None:
        if facts.final_attempts_remaining > 0:
            return NextAction("take_final", "E8")
        return NextAction("none", "E11")
    if facts.final_attempts_remaining > 0:
        return NextAction("review_final", "E9", attempt_id=facts.last_final_attempt_id)
    return NextAction("none", "E9c", attempt_id=facts.last_final_attempt_id)
