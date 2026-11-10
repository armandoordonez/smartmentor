"""Máquinas de estados de la inscripción, el paso y el intento: todos los caminos de 5.1."""

import pytest

from app.common.exceptions import InvalidStateTransitionError
from app.domains.learning_paths.states import (
    ATTEMPT_TRANSITIONS,
    CLOSED_ENROLLMENT,
    ENROLLMENT_TRANSITIONS,
    STEP_TRANSITIONS,
    AttemptStatus,
    EnrollmentStatus,
    ProgressFacts,
    StepState,
    StepStatus,
    check_attempt_transition,
    check_enrollment_transition,
    check_step_transition,
    next_action,
    refresh_availability,
)

# Caminos del diagrama de la inscripción (design/01/estados.md)
ENROLLMENT_PATHS = [
    ("enrolled", "profiling"),
    ("enrolled", "diagnosing"),
    ("profiling", "diagnosing"),
    ("diagnosing", "objective_pending"),
    ("objective_pending", "in_path"),
    ("in_path", "final_ready"),
    ("final_ready", "completed"),
    ("final_ready", "final_ready"),
    *[(s.value, "abandoned") for s in EnrollmentStatus if s not in CLOSED_ENROLLMENT],
    *[(s.value, "withdrawn") for s in EnrollmentStatus if s not in CLOSED_ENROLLMENT],
]

STEP_PATHS = [
    ("blocked", "pending"),
    ("pending", "in_progress"),
    ("in_progress", "passed"),
    ("in_progress", "in_progress"),
    ("in_progress", "attempts_exhausted"),
    ("attempts_exhausted", "in_progress"),
    ("blocked", "on_hold"),
    ("pending", "on_hold"),
    ("on_hold", "pending"),
]

ATTEMPT_PATHS = [
    ("created", "in_progress"),
    ("in_progress", "submitted"),
    ("submitted", "grading"),
    ("grading", "graded"),
    ("grading", "grading_failed"),
    ("grading_failed", "grading"),
]


@pytest.mark.parametrize(("current", "target"), ENROLLMENT_PATHS)
def test_every_enrollment_path_of_the_diagram_is_allowed(current: str, target: str) -> None:
    check_enrollment_transition(current, target)


@pytest.mark.parametrize(("current", "target"), STEP_PATHS)
def test_every_step_path_of_the_diagram_is_allowed(current: str, target: str) -> None:
    check_step_transition(current, target)


@pytest.mark.parametrize(("current", "target"), ATTEMPT_PATHS)
def test_every_attempt_path_of_the_diagram_is_allowed(current: str, target: str) -> None:
    check_attempt_transition(current, target)


def _forbidden(table: dict[str, frozenset[str]], values: list[str]) -> list[tuple[str, str]]:
    return [(a, b) for a in values for b in values if b not in table[a]]


@pytest.mark.parametrize(
    ("current", "target"), _forbidden(ENROLLMENT_TRANSITIONS, [s.value for s in EnrollmentStatus])
)
def test_any_other_enrollment_transition_is_rejected(current: str, target: str) -> None:
    with pytest.raises(InvalidStateTransitionError):
        check_enrollment_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"), _forbidden(STEP_TRANSITIONS, [s.value for s in StepStatus])
)
def test_any_other_step_transition_is_rejected(current: str, target: str) -> None:
    with pytest.raises(InvalidStateTransitionError):
        check_step_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"), _forbidden(ATTEMPT_TRANSITIONS, [s.value for s in AttemptStatus])
)
def test_any_other_attempt_transition_is_rejected(current: str, target: str) -> None:
    with pytest.raises(InvalidStateTransitionError):
        check_attempt_transition(current, target)


def test_closed_enrollments_have_no_way_out() -> None:
    for status in CLOSED_ENROLLMENT:
        assert ENROLLMENT_TRANSITIONS[status] == frozenset()


# --- disponibilidad de los pasos ---------------------------------------------------------------

# 1 → 2 → 3 y 1 → 4 (el tema 4 no depende del 2)
PREREQUISITES = {2: (1,), 3: (2,), 4: (1,)}


def steps(*statuses: str) -> list[StepState]:
    return [StepState(n, n, n, s) for n, s in enumerate(statuses, start=1)]


def test_a_passed_prerequisite_unblocks_its_dependents() -> None:
    changes = refresh_availability(steps("passed", "blocked", "blocked", "blocked"), PREREQUISITES)
    assert changes == {2: "pending", 4: "pending"}


def test_skipped_counts_as_done() -> None:
    changes = refresh_availability(steps("skipped", "blocked", "blocked", "blocked"), PREREQUISITES)
    assert changes == {2: "pending", 4: "pending"}


def test_an_exhausted_topic_puts_only_its_dependents_on_hold_transitively() -> None:
    changes = refresh_availability(
        steps("passed", "attempts_exhausted", "blocked", "pending"), PREREQUISITES
    )
    assert changes == {3: "on_hold"}  # el 4 sigue disponible (avance no lineal)


def test_on_hold_goes_back_when_the_prerequisite_is_resolved() -> None:
    passed = refresh_availability(steps("passed", "passed", "on_hold", "pending"), PREREQUISITES)
    assert passed == {3: "pending"}
    retrying = refresh_availability(
        steps("passed", "in_progress", "on_hold", "pending"), PREREQUISITES
    )
    assert retrying == {3: "blocked"}


def test_nothing_changes_when_everything_is_consistent() -> None:
    assert (
        refresh_availability(steps("pending", "blocked", "blocked", "blocked"), PREREQUISITES) == {}
    )


# --- next_action -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        (ProgressFacts(status="withdrawn"), "none"),
        (ProgressFacts(status="abandoned"), "none"),
        (ProgressFacts(status="enrolled"), "complete_profile"),
        (ProgressFacts(status="profiling"), "complete_profile"),
        (ProgressFacts(status="diagnosing"), "start_diagnostic"),
        (
            ProgressFacts(status="diagnosing", diagnostic_status="in_progress"),
            "continue_diagnostic",
        ),
        (
            ProgressFacts(status="diagnosing", diagnostic_status="scoring", diagnostic_job_id="j"),
            "wait_job",
        ),
        (ProgressFacts(status="objective_pending"), "confirm_objective"),
        (
            ProgressFacts(status="in_path", steps=tuple(steps("passed", "pending"))),
            "study_topic",
        ),
        (
            ProgressFacts(status="in_path", open_attempt_id=9, open_attempt_step_id=2),
            "continue_attempt",
        ),
        (
            ProgressFacts(status="in_path", grading_attempt_id=9, grading_job_id="j"),
            "wait_job",
        ),
        (
            ProgressFacts(status="in_path", steps=tuple(steps("attempts_exhausted", "on_hold"))),
            "wait_instructor",
        ),
        (ProgressFacts(status="final_ready", final_attempts_remaining=3), "take_final"),
        (
            ProgressFacts(
                status="final_ready", last_final_attempt_id=5, final_attempts_remaining=2
            ),
            "review_final",
        ),
        (
            ProgressFacts(
                status="final_ready", last_final_attempt_id=5, final_attempts_remaining=0
            ),
            "none",
        ),
        (ProgressFacts(status="completed"), "answer_survey"),
        (ProgressFacts(status="completed", has_survey=True), "view_badge"),
    ],
)
def test_next_action_for_each_situation(facts: ProgressFacts, expected: str) -> None:
    assert next_action(facts).type == expected


def test_next_action_points_to_the_first_available_step_and_the_job() -> None:
    action = next_action(
        ProgressFacts(status="in_path", steps=tuple(steps("passed", "in_progress")))
    )
    assert action.step_id == 2
    assert action.screen == "E6"
    waiting = next_action(
        ProgressFacts(status="diagnosing", diagnostic_status="scoring", diagnostic_job_id="job-1")
    )
    assert waiting.job_id == "job-1"
    final_attempt = next_action(ProgressFacts(status="final_ready", open_attempt_id=7))
    assert final_attempt.screen == "E8"
    assert final_attempt.step_id is None
