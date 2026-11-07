"""Personalised learning path: result of the synchronous ``path.sequence`` task (no LLM)."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel

StepStatus = Literal[
    "skipped",
    "blocked",
    "pending",
    "in_progress",
    "passed",
    "attempts_exhausted",
    "on_hold",
]
InclusionReason = Literal[
    "skipped_mastered",
    "weak_prerequisite",
    "objective_focus",
    "required_by_path",
    "mandatory",
    "fixed_path",
]
PilotArm = Literal["personalized", "fixed"]


class PathStep(ContractModel):
    step_order: int = Field(ge=1)
    topic_id: str
    status: StepStatus
    inclusion_reason: InclusionReason
    diagnostic_level: float | None = Field(default=None, ge=0, le=100)


class LearningPath(ContractModel):
    algorithm: str = Field(description="Algorithm and version, e.g. topological_threshold v1")
    mastery_skip_threshold: float = Field(ge=0, le=100)
    pilot_arm: PilotArm | None = None
    steps: list[PathStep] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_steps(self) -> Self:
        orders = [s.step_order for s in self.steps]
        if orders != list(range(1, len(self.steps) + 1)):
            raise ValueError("step_order must be 1..n in list order")
        topics = [s.topic_id for s in self.steps]
        if len(topics) != len(set(topics)):
            raise ValueError("a topic appears more than once in the path")
        for step in self.steps:
            if (step.status == "skipped") != (step.inclusion_reason == "skipped_mastered"):
                raise ValueError(f"{step.topic_id}: skipped <=> inclusion_reason skipped_mastered")
            if self.pilot_arm == "fixed" and step.inclusion_reason != "fixed_path":
                raise ValueError(
                    f"{step.topic_id}: the fixed arm includes every topic as fixed_path"
                )
        return self
