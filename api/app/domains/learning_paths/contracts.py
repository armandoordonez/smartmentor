"""Contrato de `path.sequence` (`learning_path.v1`): espejo de `prompts/schemas/learning_path.v1.json`.

La prueba de contrato compara la salida de `FakeAiService` con el JSON Schema real y con este modelo.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

StepStatusName = Literal[
    "skipped", "blocked", "pending", "in_progress", "passed", "attempts_exhausted", "on_hold"
]
InclusionReasonName = Literal[
    "skipped_mastered",
    "weak_prerequisite",
    "objective_focus",
    "required_by_path",
    "mandatory",
    "fixed_path",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SequencedStep(_Strict):
    step_order: Annotated[int, Field(ge=1)]
    topic_id: str
    status: StepStatusName
    inclusion_reason: InclusionReasonName
    diagnostic_level: Annotated[float, Field(ge=0, le=100)] | None = None


class LearningPathV1(_Strict):
    """`learning_path.v1`: pasos ordenados con estado y motivo de inclusión."""

    algorithm: str
    mastery_skip_threshold: Annotated[float, Field(ge=0, le=100)]
    pilot_arm: Literal["personalized", "fixed"] | None = None
    steps: Annotated[list[SequencedStep], Field(min_length=1)]
