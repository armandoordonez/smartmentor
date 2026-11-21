"""Modo del contenido de un paso (E6): estudio, repaso o no disponible (B-025)."""

import pytest

from app.common.exceptions import ConflictError
from app.domains.assessments.service import content_mode
from app.domains.learning_paths.states import StepStatus


@pytest.mark.parametrize(
    "status", [StepStatus.PENDING, StepStatus.IN_PROGRESS, StepStatus.ATTEMPTS_EXHAUSTED]
)
def test_open_steps_are_studied(status: StepStatus) -> None:
    assert content_mode(status) == "study"


@pytest.mark.parametrize("status", [StepStatus.PASSED, StepStatus.SKIPPED])
def test_passed_and_skipped_steps_are_reviewed(status: StepStatus) -> None:
    assert content_mode(status) == "review"


@pytest.mark.parametrize("status", [StepStatus.BLOCKED, StepStatus.ON_HOLD])
def test_blocked_and_on_hold_steps_are_not_available(status: StepStatus) -> None:
    with pytest.raises(ConflictError) as raised:
        content_mode(status)
    assert raised.value.code == "STEP_NOT_AVAILABLE"
