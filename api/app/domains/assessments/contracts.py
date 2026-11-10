"""Contratos que ingiere el dominio de evaluaciones (espejo de `prompts/schemas/*.json`).

- `diagnostic_finalization.v1` (`diagnostic.finalize`) y `diagnostic_result.v1` (`levels.estimate`).
- `grading.v1` (`grading.short_answer`).
- `assessment_item_bank.v1` (`items.generate_quiz_bank` bajo demanda, U1b).
La prueba de contrato valida las salidas de `FakeAiService` contra el JSON Schema y estos
modelos.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Score = Annotated[float, Field(ge=0, le=100)]
Bloom = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Meta(_Strict):
    prompt_id: str
    prompt_version: Annotated[str, StringConstraints(pattern=r"^v\d+$")]
    model: str
    generated_at: datetime
    input_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    from_cache: bool = False


class LevelWeights(_Strict):
    test: Annotated[float, Field(ge=0, le=1)]
    profile: Annotated[float, Field(ge=0, le=1)]
    resume: Annotated[float, Field(ge=0, le=1)]


class LevelThresholds(_Strict):
    mastery_skip_threshold: Score
    reinforce_cutoff: Score


class TopicLevel(_Strict):
    topic_id: str
    test_score: Score | None
    profile_similarity: Annotated[float, Field(ge=-1, le=1)] | None
    profile_prior: Score | None
    resume_prior: Score | None
    weights: LevelWeights
    level: Score
    classification: Literal["mastered", "to_reinforce", "to_learn"]


class DiagnosticResultV1(_Strict):
    algorithm: str
    configured_weights: LevelWeights
    thresholds: LevelThresholds
    level_by_topic: Annotated[list[TopicLevel], Field(min_length=1)]
    overall_score: Score


class ObjectiveV1(_Strict):
    origin: Literal["path_default", "llm_proposed", "learner_edited"]
    statement: Annotated[str, StringConstraints(min_length=1)]
    bloom_verb: Annotated[str, StringConstraints(min_length=1)]
    content: Annotated[str, StringConstraints(min_length=1)]
    criterion: Annotated[str, StringConstraints(min_length=1)]
    focus_topics: list[str]
    rationale: str
    meta: Meta | None = None


class DiagnosticFinalizationV1(_Strict):
    diagnostic_result: DiagnosticResultV1
    objective: ObjectiveV1


class CriterionResult(_Strict):
    criterion: str
    met: bool
    points: Annotated[float, Field(gt=0, le=1)]
    points_awarded: Annotated[float, Field(ge=0, le=1)]
    evidence: str


class GradingV1(_Strict):
    item_id: str
    item_type: Literal["multiple_choice", "short_answer"]
    grader: Literal["rule", "llm_judge", "human"]
    approval_rule: Literal["single_correct_option", "min_criteria_ratio"]
    min_criteria_ratio: Annotated[float, Field(gt=0, le=1)] | None = None
    score: Score
    is_correct: bool
    criteria_met: Annotated[int, Field(ge=0)]
    criteria_total: Annotated[int, Field(ge=0)]
    rubric_detail: list[CriterionResult]
    feedback: str
    meta: Meta | None = None


class RubricCriterion(_Strict):
    criterion: Annotated[str, StringConstraints(min_length=1)]
    points: Annotated[float, Field(gt=0, le=1)]


class AssessmentItemV1(_Strict):
    id: Annotated[str, StringConstraints(min_length=1)]
    topic_id: str
    outcome_id: str
    source: Literal["diagnostic", "topic_quiz", "final", "retention"]
    item_type: Literal["multiple_choice", "short_answer"]
    bloom_level: Bloom
    difficulty: Annotated[int, Field(ge=1, le=3)]
    stem: Annotated[str, StringConstraints(min_length=1)]
    options: list[str]
    correct_option: Annotated[int, Field(ge=0, le=3)] | None = None
    model_answer: str
    rubric: list[RubricCriterion]
    equivalence_group: str | None = None


class ItemReview(_Strict):
    item_id: str
    single_correct_answer: bool
    clear_stem: bool
    bloom_matches: bool
    aligned_with_outcome: bool
    issues: list[str]


class AssessmentItemBankV1(_Strict):
    topic_id: str | None = None
    items: Annotated[list[AssessmentItemV1], Field(min_length=1)]
    item_reviews: list[ItemReview]
    discarded_item_ids: list[str]
    meta: Meta
