"""Modelos de los resultados de contenido que la API ingiere (espejo de `prompts/schemas/*.json`).

Igual que `ai_gateway/contracts.py`: la imagen de la API no incluye `prompts/`, así que la
validación usa estos modelos y la prueba de contrato los compara con el JSON Schema real.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.domains.ai_gateway.contracts import BloomName, ResultMeta


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- topic_explanation.v1 ---------------------------------------------------------------------


class CitedSource(_Strict):
    n: Annotated[int, Field(ge=1)]
    source_id: str
    title: str
    url: str
    license: str | None = None


class ExplanationSection(_Strict):
    heading: Annotated[str, StringConstraints(min_length=1)]
    body: Annotated[str, StringConstraints(min_length=1)]


class TopicExplanationBody(_Strict):
    """Lo que el instructor edita en D5d: la explicación sin `meta` ni datos de revisión."""

    title: Annotated[str, StringConstraints(min_length=1)]
    sections: Annotated[list[ExplanationSection], Field(min_length=1)]
    worked_example: str
    summary: str
    reflection_questions: list[str] = Field(default_factory=list)
    gaps_detected: list[str] = Field(default_factory=list)
    sources: Annotated[list[CitedSource], Field(min_length=1)]


class TopicExplanationV1(TopicExplanationBody):
    topic_id: str
    kind: Literal["main", "remedial"]
    audience: Literal["all_learners", "enrollment"]
    version: Annotated[str, StringConstraints(pattern=r"^\d+\.\d+$")] = "1.0"
    edited_by_user_id: int | None = None
    faithfulness: Annotated[float, Field(ge=0, le=1)] | None = None
    unsupported_claims: list[str] = Field(default_factory=list)
    meta: ResultMeta


# --- faithfulness_check.v1 --------------------------------------------------------------------


class Claim(_Strict):
    text: Annotated[str, StringConstraints(min_length=1)]
    citations: list[int]
    supported: bool
    comment: str


class FaithfulnessCheckV1(_Strict):
    claims: Annotated[list[Claim], Field(max_length=15)]
    faithfulness: Annotated[float, Field(ge=0, le=1)]
    unsupported_claims: list[str]
    meta: ResultMeta


# --- assessment_item_bank.v1 e item_review.v1 -------------------------------------------------


class RubricCriterion(_Strict):
    criterion: Annotated[str, StringConstraints(min_length=1)]
    points: Annotated[float, Field(gt=0, le=1)]


class BankItem(_Strict):
    id: Annotated[str, StringConstraints(min_length=1)]
    topic_id: str
    outcome_id: str
    source: Literal["diagnostic", "topic_quiz", "final", "retention"]
    item_type: Literal["multiple_choice", "short_answer"]
    bloom_level: BloomName
    difficulty: Annotated[int, Field(ge=1, le=3)]
    stem: Annotated[str, StringConstraints(min_length=1)]
    options: list[str]
    correct_option: Annotated[int, Field(ge=0, le=3)] | None = None
    model_answer: str
    rubric: list[RubricCriterion]
    equivalence_group: str | None = None

    @model_validator(mode="after")
    def _shape(self) -> "BankItem":
        if self.item_type == "multiple_choice":
            if len(self.options) != 4 or self.correct_option is None:
                raise ValueError("multiple choice needs 4 options and correct_option")
        elif self.options or self.correct_option is not None or not self.rubric:
            raise ValueError("short answer needs a rubric and no options")
        return self


class ItemReviewEntry(_Strict):
    item_id: str
    single_correct_answer: bool
    clear_stem: bool
    bloom_matches: bool
    aligned_with_outcome: bool
    issues: list[str]


class AssessmentItemBankV1(_Strict):
    topic_id: str | None = None
    items: Annotated[list[BankItem], Field(min_length=1)]
    item_reviews: list[ItemReviewEntry]
    discarded_item_ids: list[str]
    meta: ResultMeta


class ItemReviewResultV1(_Strict):
    reviews: Annotated[list[ItemReviewEntry], Field(min_length=1)]
    discarded_item_ids: list[str] = Field(default_factory=list)
    meta: ResultMeta


# --- video_resource.v1 ------------------------------------------------------------------------


class VideoCandidateOut(_Strict):
    youtube_video_id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{11}$")]
    title: Annotated[str, StringConstraints(min_length=1)]
    url: str
    channel: str = ""
    origin: Literal["youtube_api", "instructor"]
    duration_seconds: Annotated[int, Field(ge=1)] | None = None
    language: Annotated[str, StringConstraints(pattern=r"^[a-z]{2}$")] | None = None
    has_captions: bool | None = None
    characterization: str | None = None
    characterization_source: Literal["metadata", "transcript", "instructor"] | None = None
    similarity: Annotated[float, Field(ge=-1, le=1)] | None = None
    rank: Annotated[int, Field(ge=1)]
    relevance_judgment: bool | None = None


class VideoResourceV1(_Strict):
    topic_id: str
    origin: Literal["youtube_api", "instructor", "none"]
    embedding_model: str
    candidates: list[VideoCandidateOut]
    selected_video_id: str | None = None
    backup_video_ids: list[str] = Field(default_factory=list)
