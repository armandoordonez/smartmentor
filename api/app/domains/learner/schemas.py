"""Contratos HTTP de las rutas `/me` del aprendiz (docs/contracts/api-v2.md, sección 4)."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.common.schemas import RequestSchema, UtcDatetime
from app.domains.learning_paths.schemas import NextActionResponse


class LearnerAnswerBody(RequestSchema):
    """`LearnerAnswer` (forma de `simulated_answers.v1`) con `item_id` entero."""

    item_id: Annotated[int, Field(ge=1)]
    selected_option: Annotated[int, Field(ge=0, le=3)] | None = None
    dont_know: bool = False
    text_answer: Annotated[str, Field(max_length=4000)] | None = None


class AnswersBody(RequestSchema):
    answers: Annotated[list[LearnerAnswerBody], Field(max_length=200)]


class SavedResponse(BaseModel):
    saved: int


class LearnerAnswerResponse(BaseModel):
    item_id: int
    selected_option: int | None
    dont_know: bool
    text_answer: str | None


class ItemForLearner(BaseModel):
    """Ítem sin `correct_option`, `model_answer` ni `rubric`."""

    item_id: int
    topic_id: int
    stem: str
    item_type: str
    options: list[str]
    allows_dont_know: bool = True


class DiagnosticResponse(BaseModel):
    id: int
    status: str
    items: list[ItemForLearner]
    answers: list[LearnerAnswerResponse]
    submitted_at: UtcDatetime | None


class TopicLevelResponse(BaseModel):
    topic_id: int
    name: str
    test_score: float | None
    profile_prior: float | None
    resume_prior: float | None
    weights: dict[str, float]
    level: float
    classification: str


class ProposedObjective(BaseModel):
    statement: str
    bloom_verb: str
    content: str
    criterion: str
    origin: str | None


class DiagnosticResultResponse(BaseModel):
    status: str
    level_by_topic: list[TopicLevelResponse]
    overall_score: float
    proposed_objective: ProposedObjective | None


class AttemptCreate(RequestSchema):
    assessment_type: Literal["topic", "retention"] = "topic"


class AttemptResponse(BaseModel):
    id: int
    assessment_type: str
    status: str
    step_id: int | None
    attempt_number: int
    items: list[ItemForLearner]
    answers: list[LearnerAnswerResponse]
    uses_extra_grant: bool
    created_at: UtcDatetime


class AttemptCounters(BaseModel):
    used: int
    max: int
    remaining: int


class GradedAnswer(BaseModel):
    attempt_answer_id: int
    item_id: int
    grading: dict[str, Any] | None
    review_requested: bool


class AttemptResultResponse(BaseModel):
    attempt_id: int
    assessment_type: str
    status: str
    score: float | None
    passed: bool | None
    pass_threshold: float
    answers: list[GradedAnswer]
    remedial_resource_id: int | None
    attempts: AttemptCounters
    next_action: NextActionResponse


class ReviewRequestBody(RequestSchema):
    comment: Annotated[str, Field(max_length=2000)] | None = None


class ReviewRequestResponse(BaseModel):
    alert_id: int | None


class LearningOutcomeBrief(BaseModel):
    id: int
    statement: str
    bloom_level: str | None


class StepTopic(BaseModel):
    id: int
    name: str
    learning_outcomes: list[LearningOutcomeBrief]


class QuizRules(BaseModel):
    pass_threshold: float
    items_per_attempt: int
    short_answer_min_criteria_ratio: float


class StepContentResponse(BaseModel):
    step_id: int
    status: str
    topic: StepTopic
    explanation: dict[str, Any] | None
    personal_example: dict[str, Any] | None
    video: dict[str, Any] | None
    quiz_rules: QuizRules
    attempts: dict[str, int]


class WeakTopicResponse(BaseModel):
    topic_id: int
    name: str
    score: float
    resource_id: int | None


class ReviewPlanResponse(BaseModel):
    weak_topics: list[WeakTopicResponse]


class BadgeSummary(BaseModel):
    public_id: str
    enrollment_id: int
    name: str
    course_name: str
    learning_path_name: str
    issued_at: UtcDatetime | None
    assertion_url: str
    image_url: str


class SurveyBody(RequestSchema):
    likert: Annotated[
        dict[str, Annotated[int, Field(ge=1, le=5)]], Field(max_length=50, default_factory=dict)
    ]
    sus_items: Annotated[
        list[Annotated[int, Field(ge=1, le=5)]], Field(min_length=10, max_length=10)
    ]
    comment: Annotated[str, Field(max_length=4000)] | None = None


class SurveyResponseBody(BaseModel):
    id: int
    sus_score: float


class EventBody(RequestSchema):
    enrollment_id: Annotated[int, Field(ge=1)]
    event_type: Annotated[str, Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_.]*$")]
    topic_id: Annotated[int, Field(ge=1)] | None = None
    occurred_at: datetime
    payload: dict[str, Any] | None = None


class EventsBody(RequestSchema):
    events: Annotated[list[EventBody], Field(min_length=1, max_length=100)]


class EventsAccepted(BaseModel):
    accepted: int
