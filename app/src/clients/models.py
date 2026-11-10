"""Modelos Pydantic del contrato de la API (`docs/contracts/api-v2.md`).

Cada modelo sigue un esquema del contrato. Donde el contrato no fija la forma (`LearningPathCard`,
`Consent`, `BadgeSummary`…), el modelo es una propuesta y se anota en la bitácora de la fase.
Cuando exista el OpenAPI de la API (Fase 3), estos modelos se contrastan con él.

Las respuestas reales se leen con `extra="ignore"` (un campo nuevo de la API no rompe la interfaz);
las pruebas validan fixtures y ejemplos del contrato con `extra="forbid"` para detectar deriva.
"""

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["learner", "instructor", "admin"]
ROLES: tuple[Role, ...] = ("learner", "instructor", "admin")

ConsentType = Literal["data_processing", "pilot_research"]
RequestType = Literal["deletion", "access", "rectification"]
EducationLevel = Literal["secondary", "technical", "undergraduate", "postgraduate", "other", "none"]
ExperienceBand = Literal["none", "less_than_1_year", "1_3_years", "3_5_years", "more_than_5_years"]
CefrLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]

EnrollmentStatus = Literal[
    "enrolled",
    "profiling",
    "diagnosing",
    "objective_pending",
    "in_path",
    "final_ready",
    "completed",
    "abandoned",
    "withdrawn",
]
NextActionType = Literal[
    "complete_profile",
    "start_diagnostic",
    "continue_diagnostic",
    "wait_job",
    "confirm_objective",
    "study_topic",
    "continue_attempt",
    "view_attempt_result",
    "wait_instructor",
    "take_final",
    "review_final",
    "answer_survey",
    "view_badge",
    "none",
]
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
AttemptStatus = Literal[
    "created", "in_progress", "submitted", "grading", "graded", "grading_failed"
]
AssessmentType = Literal["topic", "final", "retention"]
ItemType = Literal["multiple_choice", "short_answer"]
TopicClassification = Literal["mastered", "to_reinforce", "to_learn"]
ObjectiveOrigin = Literal["path_default", "llm_proposed", "learner_edited"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]
PilotArm = Literal["personalized", "fixed"]
PathLevel = Literal["basic", "intermediate", "advanced"]
PathSection = Literal["paths", "applied_ai"]
PathTag = Literal["recommended", "new", "popular", "new_anthropic", "new_google"]
BloomLevel = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]
VideoRating = Literal["useful", "audio_issue", "outdated", "too_long"]


class ApiModel(BaseModel):
    """Base de los modelos: ignora campos desconocidos, como pide la lectura tolerante."""

    model_config = ConfigDict(extra="ignore")


T = TypeVar("T", bound=BaseModel)


class Page(ApiModel, Generic[T]):  # noqa: UP046 (Pydantic exige Generic[T] explícito)
    """Lista paginada `{"items", "total", "limit", "offset"}` (contrato, sección 1)."""

    items: list[T]
    total: int
    limit: int
    offset: int


# --- Usuario actual, consentimientos y perfil (sección 2) -----------------------------------


class ConsentGrant(ApiModel):
    granted: bool
    document_version: str | None = None
    granted_at: datetime | None = None


class ConsentStatus(ApiModel):
    data_processing: ConsentGrant
    pilot_research: ConsentGrant


class ProfileCompleteness(ApiModel):
    description: bool
    resume: bool
    percent: int


class Me(ApiModel):
    """Respuesta de `GET /me`: el usuario, sus roles y lo que falta para entrar (CU-34, CU-35)."""

    id: int
    email: str
    full_name: str
    roles: list[Role]
    role_labels: dict[Role, str]
    role_short_labels: dict[Role, str]
    default_role: Role
    is_new_user: bool
    consent_status: ConsentStatus
    requires_consent: bool
    profile_completeness: ProfileCompleteness
    second_factor: bool


class Language(ApiModel):
    code: str
    cefr_level: CefrLevel


class Profile(ApiModel):
    description: str | None = None
    education_level: EducationLevel | None = None
    qualification_title: str | None = None
    job_title: str | None = None
    experience_band: ExperienceBand | None = None
    tools: list[str] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    resume_completed_at: datetime | None = None
    recalculated_enrollment_ids: list[int] = Field(default_factory=list)


class ProfileUpdate(ApiModel):
    """Cuerpo de `PUT /me/profile`."""

    description: str | None = None
    education_level: EducationLevel | None = None
    qualification_title: str | None = None
    job_title: str | None = None
    experience_band: ExperienceBand | None = None
    tools: list[str] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)


class Consent(ApiModel):
    """Propuesta: el contrato solo dice `Consent` sin detallar sus campos."""

    consent_type: ConsentType
    granted: bool
    document_version: str | None = None
    granted_at: datetime | None = None
    revoked_at: datetime | None = None


class DataSubjectRequest(ApiModel):
    id: int
    request_type: RequestType
    status: Literal["pending"]


# --- Catálogo e inscripción (secciones 3 y 4) ------------------------------------------------


class LearningPathCard(ApiModel):
    """Propuesta: el contrato dice «`LearningPathCard`» sin detallar sus campos (E1)."""

    id: int
    name: str
    description: str | None = None
    group_label: str | None = None
    section: PathSection = "paths"
    tags: list[PathTag] = Field(default_factory=list)
    topics_count: int
    estimated_minutes: int
    level: PathLevel


class LearningPathRef(ApiModel):
    id: int
    name: str
    group_label: str | None = None


class Objective(ApiModel):
    statement: str
    bloom_verb: str
    content: str
    criterion: str
    origin: ObjectiveOrigin


class Progress(ApiModel):
    steps_total: int
    steps_done: int
    percent: int


class NextAction(ApiModel):
    """Qué sigue en la inscripción. La app navega por este objeto y nunca deduce estados."""

    type: NextActionType
    step_id: int | None = None
    attempt_id: int | None = None
    job_id: str | None = None
    screen: str | None = None


class Enrollment(ApiModel):
    id: int
    learning_path: LearningPathRef
    status: EnrollmentStatus
    objective: Objective | None = None
    progress: Progress
    pilot_arm: PilotArm | None = None
    next_action: NextAction
    created_at: datetime
    completed_at: datetime | None = None


# --- Trabajos de IA (sección 7) --------------------------------------------------------------


class JobAccepted(ApiModel):
    job_id: str
    status: JobStatus
    poll_url: str


class JobError(ApiModel):
    code: str
    retryable: bool = False


class Job(ApiModel):
    job_id: str
    job_type: str
    status: JobStatus
    progress_label: str | None = None
    ingested: bool
    next_action: NextAction | None = None
    error: JobError | None = None


# --- Diagnóstico, intentos y ruta (secciones 4 y 4.1) ----------------------------------------


class AssessmentItem(ApiModel):
    """Pregunta sin solución (`correct_option`, `model_answer` y `rubric` nunca llegan a la app)."""

    item_id: int
    topic_id: int
    stem: str
    item_type: ItemType
    options: list[str] = Field(default_factory=list)
    allows_dont_know: bool = False
    topic_name: str | None = None
    """Propuesta (F07b): nombre del tema, para «Tema · Regresión lineal» (E3, E6b, E8)."""
    bloom_level: BloomLevel | None = None
    """Propuesta (F07b): nivel de Bloom de la pregunta («Bloom · Aplicar»)."""
    rubric_summary: str | None = None
    """Propuesta (F07b): rúbrica visible de una respuesta corta («CÓMO SE CALIFICA», E6c)."""


class LearnerAnswer(ApiModel):
    item_id: int
    selected_option: int | None = None
    dont_know: bool = False
    text_answer: str | None = None


class Diagnostic(ApiModel):
    id: int
    status: Literal["created", "in_progress", "submitted", "scored"]
    items: list[AssessmentItem]
    answers: list[LearnerAnswer] = Field(default_factory=list)
    submitted_at: datetime | None = None


class LevelWeights(ApiModel):
    test: float
    profile: float
    resume: float


class TopicLevel(ApiModel):
    topic_id: int
    name: str
    test_score: float | None = None
    profile_similarity: float | None = None
    profile_prior: float | None = None
    resume_prior: float | None = None
    weights: LevelWeights
    level: float
    classification: TopicClassification


class DiagnosticResult(ApiModel):
    status: Literal["scored"]
    level_by_topic: list[TopicLevel]
    overall_score: float
    proposed_objective: Objective


class PathStep(ApiModel):
    step_id: int
    step_order: int
    topic_id: int
    name: str
    status: StepStatus
    inclusion_reason: InclusionReason
    diagnostic_level: float | None = None
    estimated_minutes: int | None = None
    attempts_used: int
    max_attempts: int
    extra_attempts_granted: int
    best_score: float | None = None


class PathSavings(ApiModel):
    skipped_topics: int
    skipped_minutes: int


class FinalAssessmentState(ApiModel):
    locked: bool
    attempts_used: int
    max_attempts: int
    pass_threshold: float


class PathDetail(ApiModel):
    enrollment_id: int
    steps: list[PathStep]
    savings: PathSavings
    final: FinalAssessmentState


class LearningOutcome(ApiModel):
    id: int
    statement: str
    bloom_level: BloomLevel


class StepTopic(ApiModel):
    id: int
    name: str
    learning_outcomes: list[LearningOutcome] = Field(default_factory=list)


class StepExplanation(ApiModel):
    resource_id: int
    version: str
    prompt_version: str
    content: dict[str, Any]
    """`topic_explanation.v1` sin `meta` (esquema en `prompts/schemas/`)."""


class StepVideo(ApiModel):
    video_candidate_id: int
    youtube_video_id: str
    title: str
    duration_seconds: int
    is_backup: bool = False


class QuizRules(ApiModel):
    pass_threshold: float
    items_per_attempt: int
    short_answer_min_criteria_ratio: float


class AttemptsCounter(ApiModel):
    used: int
    max: int
    extra_granted: int = 0
    remaining: int


class StepContent(ApiModel):
    step_id: int
    topic: StepTopic
    explanation: StepExplanation | None = None
    personal_example: dict[str, Any] | None = None
    video: StepVideo | None = None
    quiz_rules: QuizRules
    attempts: AttemptsCounter


class Attempt(ApiModel):
    id: int
    assessment_type: AssessmentType
    status: AttemptStatus
    step_id: int | None = None
    items: list[AssessmentItem]
    answers: list[LearnerAnswer] = Field(default_factory=list)
    uses_extra_grant: bool = False
    created_at: datetime


class AnswerResult(ApiModel):
    attempt_answer_id: int
    item_id: int
    grading: dict[str, Any]
    """`grading.v1` sin `meta` (esquema en `prompts/schemas/`)."""
    review_requested: bool = False


class AttemptsSummary(ApiModel):
    used: int
    max: int
    remaining: int


class AttemptResult(ApiModel):
    attempt_id: int
    status: AttemptStatus
    score: float
    passed: bool
    pass_threshold: float
    answers: list[AnswerResult]
    remedial_resource_id: int | None = None
    attempts: AttemptsSummary
    next_action: NextAction


class WeakTopic(ApiModel):
    topic_id: int
    name: str
    score: float
    resource_id: int | None = None


class ReviewPlan(ApiModel):
    weak_topics: list[WeakTopic]


class BadgeSummary(ApiModel):
    """Propuesta: el contrato dice «`BadgeSummary`» sin detallar sus campos (E10, E12)."""

    public_id: str
    enrollment_id: int
    learning_path_name: str
    issued_at: datetime
    assertion_url: str
    image_url: str
