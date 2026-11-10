"""Modelos del contrato de las rutas del instructor y del administrador (`api-v2.md`, 5 y 6).

Siguen el mismo criterio que `models.py`: las respuestas reales se leen con `extra="ignore"` y las
pruebas validan los fixtures con `extra="forbid"`. El contrato fija las rutas y algunos cuerpos
(`TopicWrite`, `PathSettings`) pero deja sin detallar `Course`, `Dashboard`, `Pilot`, el log del
LLM y las métricas (sección 8 del contrato): esos modelos son **propuestas** y se anotan en la
bitácora F07c para contrastarlas con el OpenAPI cuando exista.
"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from clients.models import (
    ApiModel,
    BloomLevel,
    EnrollmentStatus,
    ItemType,
    LearningPathRef,
    LevelWeights,
    Objective,
    PilotArm,
    Role,
    TopicClassification,
)

# --- Curso, temas y grafo (D1 a D2d) ---------------------------------------------------------

CourseStatus = Literal[
    "draft",
    "extracting",
    "extraction_failed",
    "in_review",
    "generating_content",
    "published",
    "archived",
]
TopicReviewStatus = Literal["unchanged", "corrected", "added", "deleted"]
TopicOrigin = Literal["llm", "instructor"]
EmbeddingStatus = Literal["generated", "pending"]


class UserRef(ApiModel):
    id: int
    full_name: str


class SyllabusInfo(ApiModel):
    filename: str | None = None
    pages: int | None = None
    characters: int | None = None


class Course(ApiModel):
    """Propuesta: el contrato dice `Course` sin detallar sus campos (D1, AD5)."""

    id: int
    name: str
    description: str | None = None
    status: CourseStatus
    learning_path: LearningPathRef | None = None
    owner: UserRef | None = None
    topics_count: int = 0
    enrolled_count: int = 0
    syllabus: SyllabusInfo | None = None
    extraction_job_id: str | None = None


class CourseCreate(ApiModel):
    """Cuerpo de `POST /courses`."""

    name: str
    description: str | None = None
    learning_path_name: str
    group_label: str | None = None


class LearningOutcomeWrite(ApiModel):
    id: int | None = None
    statement: str
    bloom_level: BloomLevel


class TopicWrite(ApiModel):
    """Cuerpo de `POST /courses/{id}/topics` y `PUT /topics/{id}` (contrato, sección 5)."""

    name: str
    description: str | None = None
    subtopics: list[str] = Field(default_factory=list)
    position: int
    estimated_minutes: int | None = None
    is_mandatory: bool = False
    bloom_level: BloomLevel
    learning_outcomes: list[LearningOutcomeWrite] = Field(default_factory=list)
    prerequisite_topic_ids: list[int] = Field(default_factory=list)


class CourseTopic(TopicWrite):
    id: int
    review_status: TopicReviewStatus = "unchanged"
    origin: TopicOrigin = "llm"
    embedding_status: EmbeddingStatus | None = None


class ReviewCounts(ApiModel):
    unchanged: int
    corrected: int
    added: int
    deleted: int


class CourseTopics(ApiModel):
    topics: list[CourseTopic]
    review_counts: ReviewCounts


class GraphNodeDoc(ApiModel):
    id: int
    name: str
    position: int


class GraphEdgeDoc(BaseModel):
    """Flecha del grafo: de un prerrequisito (`from`) al tema que lo necesita (`to`)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    source: int = Field(alias="from")
    target: int = Field(alias="to")
    origin: TopicOrigin = "llm"


class TopicGraphDoc(ApiModel):
    nodes: list[GraphNodeDoc]
    edges: list[GraphEdgeDoc]


class MetricTriple(ApiModel):
    precision: float
    recall: float
    f1: float


class ExtractionMetrics(ApiModel):
    topics: MetricTriple
    prerequisites: MetricTriple
    corrections: int


# --- Ruta, avance y detalle del aprendiz (D3 a D4c) -------------------------------------------


class DefaultObjective(ApiModel):
    bloom_verb: str | None = None
    content: str | None = None
    criterion: str | None = None


class PathSettings(ApiModel):
    """Cuerpo y respuesta de `PATCH /learning-paths/{id}/settings` (contrato, sección 5)."""

    topic_pass_threshold: int
    final_pass_threshold: int
    mastery_skip_threshold: int
    max_attempts: int
    short_answer_min_ratio: float
    level_weights: LevelWeights
    default_objective: DefaultObjective | None = None
    confirm_pilot_change: bool = False


MasteryStatus = Literal[
    "skipped",
    "passed",
    "in_progress",
    "reinforce",
    "attempts_exhausted",
    "pending",
    "blocked",
    "on_hold",
]


class DashboardKpis(ApiModel):
    enrolled: int
    completion_rate: float
    """Fracción de 0 a 1."""
    badges_issued: int
    attempts_per_topic: float | None = None


class DashboardLearner(ApiModel):
    enrollment_id: int
    full_name: str
    status: EnrollmentStatus
    steps_done: int
    steps_total: int
    current_topic: str | None = None
    current_score: float | None = None
    """De 0 a 100."""
    badge_issued: bool = False


class DashboardTopic(ApiModel):
    topic_id: int
    position: int
    name: str


class MasteryRow(ApiModel):
    enrollment_id: int
    full_name: str
    cells: list[MasteryStatus]
    """Una celda por tema, en el orden de `Dashboard.topics`."""


class TopicStat(ApiModel):
    topic_id: int
    first_attempt_pass_rate: float | None = None
    """Fracción de 0 a 1."""
    avg_attempts: float | None = None
    abandonments: int = 0


class Dashboard(ApiModel):
    """Propuesta: el contrato dice `Dashboard` sin detallar sus campos (D3)."""

    course_id: int
    learning_path: LearningPathRef
    published: bool
    pilot_running: bool = False
    settings: PathSettings
    kpis: DashboardKpis
    learners: list[DashboardLearner]
    topics: list[DashboardTopic]
    mastery: list[MasteryRow]
    topic_stats: list[TopicStat]
    critical_topic_ids: list[int] = Field(default_factory=list)
    unread_alerts: int = 0


class LearnerTopicLevel(ApiModel):
    topic_id: int
    name: str
    level: float
    """De 0 a 1."""
    classification: TopicClassification


class LearnerAttempt(ApiModel):
    attempt_id: int
    step_id: int | None = None
    topic_name: str
    attempt_number: int
    score: float
    """De 0 a 100."""
    passed: bool
    submitted_at: datetime
    extra_grant: bool = False


class ExhaustedStep(ApiModel):
    step_id: int
    topic_name: str
    attempts_used: int
    max_attempts: int
    best_score: float | None = None
    waiting_topic_names: list[str] = Field(default_factory=list)
    """Temas que quedan «En espera» hasta que se resuelva este paso."""


class LearnerDetail(ApiModel):
    """Propuesta: el contrato dice «perfil reducido (A3c), niveles e intentos» (D4, D4b)."""

    enrollment_id: int
    user: UserRef
    learning_path: LearningPathRef
    status: EnrollmentStatus
    profile_summary: str | None = None
    resume_summary: str | None = None
    objective: Objective | None = None
    topic_levels: list[LearnerTopicLevel]
    attempts: list[LearnerAttempt]
    exhausted_steps: list[ExhaustedStep] = Field(default_factory=list)


class AttemptGrant(ApiModel):
    id: int
    attempts: int
    note: str | None = None
    created_at: datetime


# --- Revisión de contenido, videos y evaluación (D5 a D5f) ------------------------------------

ResourceReviewStatus = Literal["pending_review", "approved", "retired"]
ItemReviewStatus = Literal["auto_rejected", "pending_review", "approved", "retired"]
ResourceKind = Literal["explanation", "alternate_explanation", "video"]
VideoStatus = Literal["candidate", "in_use", "backup", "rejected"]
SampleType = Literal["random", "learner_request"]


class Resource(ApiModel):
    """Propuesta: el contrato dice `[Resource]` (todas las versiones) sin detallar campos (D5)."""

    id: int
    topic_id: int
    kind: ResourceKind
    title: str
    version: str
    prompt_version: str | None = None
    sources: list[str] = Field(default_factory=list)
    faithfulness: float | None = None
    """De 0 a 1; los videos no tienen fidelidad."""
    relevance: float | None = None
    review_status: ResourceReviewStatus
    edited_by_user_id: int | None = None
    content: dict[str, Any] | None = None
    """`topic_explanation.v1` sin `meta` (solo en los recursos de texto)."""


class AutoReview(ApiModel):
    verdict: str
    issues: list[str] = Field(default_factory=list)


class ReviewItem(ApiModel):
    """`assessment_item.v1` más su estado de revisión (contrato, `GET /topics/{id}/items`)."""

    id: int
    topic_id: int
    stem: str
    item_type: ItemType
    bloom_level: BloomLevel
    options: list[str] = Field(default_factory=list)
    correct_option: int | None = None
    model_answer: str | None = None
    rubric: list[str] = Field(default_factory=list)
    source: Literal["llm", "instructor"] = "llm"
    review_status: ItemReviewStatus
    auto_review: AutoReview | None = None


class ItemPatch(ApiModel):
    """Cuerpo de `PATCH /items/{id}`: solo viajan los campos que cambian."""

    review_status: Literal["approved", "retired"] | None = None
    stem: str | None = None
    options: list[str] | None = None
    correct_option: int | None = None
    model_answer: str | None = None
    rubric: list[str] | None = None


class VideoCandidate(ApiModel):
    id: int
    youtube_video_id: str
    title: str
    channel: str | None = None
    duration_seconds: int
    language: str
    has_subtitles: bool = False
    relevance: float | None = None
    """De 0 a 1; solo la ve el instructor (C-08)."""
    status: VideoStatus
    is_relevant: bool | None = None
    origin: Literal["youtube", "instructor"] = "youtube"


class TopicVideos(ApiModel):
    topic_id: int
    topic_name: str
    candidates: list[VideoCandidate]


QualityStatus = Literal["recommended", "observation", "under_review", "measuring"]


class QualityLabel(ApiModel):
    label: str
    count: int


class VideoQualityRow(ApiModel):
    video_candidate_id: int
    topic_id: int
    topic_label: str
    index: int | None = None
    """Índice de 0 a 100; None mientras se mide (menos de 10 calificaciones)."""
    rating_average: float | None = None
    ratings_count: int
    ratings_needed: int = 10
    watched_fully_rate: float | None = None
    quiz_effect_points: float | None = None
    reports: int = 0
    status: QualityStatus


class VideoFeedbackSummary(ApiModel):
    video_candidate_id: int
    labels: list[QualityLabel]
    comments: list[str]
    comments_total: int


class VideoQuality(ApiModel):
    rows: list[VideoQualityRow]
    feedback: list[VideoFeedbackSummary] = Field(default_factory=list)


class AnnotationItem(ApiModel):
    item_id: int
    topic_id: int
    topic_name: str
    bloom_level: BloomLevel
    stem: str
    options: list[str]
    correct_option: int | None = None
    evaluator_slot: int
    evaluator_slots_total: int = 2


class AnnotationQueue(ApiModel):
    items: list[AnnotationItem]
    annotated: int
    total: int


class AnnotationBody(ApiModel):
    single_correct: bool
    clear_stem: bool
    bloom_ok: bool
    plausible_distractors: bool
    verdict: Literal["valid", "invalid"]
    comment: str | None = None


class GradingItem(ApiModel):
    """Respuesta corta anónima, **sin** la nota del LLM (contrato, 5.1)."""

    attempt_answer_id: int
    code: str
    topic_name: str
    prompt: str
    answer: str
    criteria: list[str]


class GradingQueue(ApiModel):
    items: list[GradingItem]
    sample_done: int
    sample_total: int
    learner_requests: int
    sample_type: SampleType


class HumanCriterion(ApiModel):
    criterion: str
    met: bool
    points_awarded: float = 0


class HumanGradingBody(ApiModel):
    criteria: list[HumanCriterion]
    score: float
    sample_type: SampleType


class HumanGradingResult(ApiModel):
    """Respuesta de `POST /attempt-answers/{id}/human-gradings`: ya incluye la nota del LLM."""

    id: int
    llm_criteria_met: int
    llm_criteria_total: int
    llm_rationale: str
    prompt_version: str
    agrees: bool


# --- Administrador (AD1 a AD5) ----------------------------------------------------------------


class AdminUser(ApiModel):
    id: int
    email: str
    full_name: str
    roles: list[Role]
    active: bool = True


class UserCreate(ApiModel):
    email: str
    full_name: str
    roles: list[Role] = Field(default_factory=lambda: list[Role](["learner"]))


class LlmTaskSummary(ApiModel):
    task: str
    calls: int
    invalid_json_rate: float
    latency_p50_ms: int
    latency_p95_ms: int
    cost_usd: float


class LlmSummary(ApiModel):
    by_task: list[LlmTaskSummary]
    total_cost_usd: float


class LlmCallLog(ApiModel):
    """Propuesta: el contrato dice «paginado» sin detallar los campos del log (AD2)."""

    id: int
    task: str
    task_label: str
    model: str
    prompt_id: str
    prompt_version: str
    tokens: int
    cost_usd: float
    latency_ms: int
    created_at: datetime


MetricStatus = Literal["meets", "not_met", "report", "no_data"]
MetricUnit = Literal["ratio", "percent", "seconds", "usd", "count", "text", "topics", "minutes"]


class MetricEntry(ApiModel):
    code: str
    name: str
    priority: Literal["P1", "P2", "P3"]
    status: MetricStatus
    value: float | None = None
    value_text: str | None = None
    unit: MetricUnit = "ratio"
    goal: str
    detail: str
    """«n = 5 temas · anotación del instructor (D2)»."""


class MetricGroup(ApiModel):
    title: str
    metrics: list[MetricEntry]


class MetricsEvaluation(ApiModel):
    """Propuesta: el contrato dice «F1, κ, QWK, fidelidad, P@3, nDCG@3…» sin forma fija (AD3)."""

    cohort: str
    is_sample_data: bool = False
    groups: list[MetricGroup]


PilotStatus = Literal["draft", "randomized", "running", "closed"]


class PilotGroups(ApiModel):
    personalized: int
    fixed: int


class PilotConsents(ApiModel):
    accepted: int
    total: int


class Pilot(ApiModel):
    id: int
    learning_path: LearningPathRef
    status: PilotStatus
    starts_on: date | None = None
    ends_on: date | None = None
    delayed_posttest_on: date | None = None
    random_seed: int | None = None
    groups: PilotGroups | None = None
    consents: PilotConsents
    equivalent_items_topics: int = 0
    topics_total: int = 0


class PilotUpdate(ApiModel):
    learning_path_id: int
    starts_on: date | None = None
    ends_on: date | None = None
    delayed_posttest_on: date | None = None
    random_seed: int | None = None


class PilotReadiness(ApiModel):
    ready: bool
    missing: list[str] = Field(default_factory=list)


class FixedPathStep(ApiModel):
    step_order: int
    topic_id: int
    name: str


class FixedPathPreview(ApiModel):
    """`learning_path.v1` con `pilot_arm=fixed`, reducido a lo que muestra AD4b."""

    pilot_arm: PilotArm
    steps: list[FixedPathStep]
    final_pass_threshold: int
    mastery_skip_threshold: int


class RandomizeResult(ApiModel):
    personalized: int
    fixed: int


class AdminEnrollment(ApiModel):
    id: int
    user: UserRef
    learning_path: LearningPathRef
    pilot_arm: PilotArm | None = None
    consent_accepted: bool
    status: EnrollmentStatus
    analysis_included: bool = True
