"""Modelos de las respuestas que la interfaz recibe de la API (o de los datos de ejemplo).

Son contratos de lectura: la interfaz no calcula puntajes, estados ni umbrales; los recibe ya
resueltos. Los porcentajes van de 0 a 1.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

Role = Literal["student", "teacher", "admin"]
BloomLevel = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]
TopicLevelStatus = Literal["mastered", "reinforce", "learn"]
StepStatus = Literal["skipped", "approved", "in_progress", "pending"]
EnrollmentStatus = Literal["onboarding", "in_progress", "completed", "abandoned"]
CourseStatus = Literal["draft", "in_review", "published"]
ReviewStatus = Literal["approved", "pending", "retired"]
EmbeddingStatus = Literal["indexed", "pending"]
QuestionKind = Literal["multiple_choice", "short_answer"]


class Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class User(Model):
    id: int
    full_name: str
    email: str
    roles: tuple[Role, ...]
    active: bool = True


# --- catálogo ----------------------------------------------------------------------------------
class LearningPath(Model):
    id: int
    course_id: int
    title: str
    short_title: str
    level: str
    estimated_hours: int
    highlight: str | None = None
    topic_count: int


class Topic(Model):
    id: int
    course_id: int
    order: int
    title: str
    bloom_level: BloomLevel
    prerequisite_ids: tuple[int, ...] = ()
    estimated_minutes: int
    embedding_status: EmbeddingStatus = "indexed"


# --- inscripción y diagnóstico -------------------------------------------------------------------
class Enrollment(Model):
    id: int
    user_id: int
    learning_path_id: int
    status: EnrollmentStatus
    group: str
    enrolled_on: date
    profile_description: str | None = None
    personal_objective: str | None = None


class Question(Model):
    id: int
    topic_id: int
    bloom_level: BloomLevel
    prompt: str
    options: tuple[str, ...]
    kind: QuestionKind = "multiple_choice"


class TopicLevel(Model):
    topic_id: int
    topic_title: str
    score: float
    status: TopicLevelStatus


class Diagnostic(Model):
    enrollment_id: int
    questions: tuple[Question, ...]
    submitted: bool
    levels: tuple[TopicLevel, ...] = ()
    proposed_objective: str | None = None
    diagnostic_weight: float = 0.7


# --- ruta y temas ------------------------------------------------------------------------------
class PathSettings(Model):
    topic_threshold: float
    final_threshold: float
    max_attempts: int
    skip_threshold: float


class PathStep(Model):
    topic_id: int
    order: int
    status: StepStatus
    attempts_used: int
    last_score: float | None = None
    diagnostic_score: float | None = None


class PathProgress(Model):
    enrollment_id: int
    learning_path_id: int
    steps: tuple[PathStep, ...]
    final_available: bool
    final_passed: bool
    saved_minutes: int
    settings: PathSettings


class VideoResource(Model):
    title: str
    duration_minutes: int
    relevance: float
    url: str | None = None


class TopicContent(Model):
    topic_id: int
    explanation: str | None
    provenance: str | None
    video: VideoResource | None


class Quiz(Model):
    topic_id: int
    questions: tuple[Question, ...]
    attempt_number: int
    max_attempts: int
    threshold: float


class AnswerReview(Model):
    number: int
    prompt: str
    correct: bool


class QuizResult(Model):
    topic_id: int
    score: float
    correct_count: int
    total: int
    threshold: float
    passed: bool
    attempt_number: int
    max_attempts: int
    reviews: tuple[AnswerReview, ...]


class FinalAssessment(Model):
    learning_path_id: int
    questions: tuple[Question, ...]
    attempt_number: int
    max_attempts: int
    threshold: float


class TopicScore(Model):
    topic_id: int
    topic_title: str
    score: float


class FinalResult(Model):
    enrollment_id: int
    score: float
    passed: bool
    threshold: float
    attempt_number: int
    max_attempts: int
    topic_scores: tuple[TopicScore, ...]
    weak_topics: tuple[TopicScore, ...]


class Badge(Model):
    enrollment_id: int
    learning_path_id: int
    path_title: str
    issued_on: date
    final_score: float
    mastered_topics: int
    total_topics: int
    saved_minutes: int
    verification_url: str


# --- docente -----------------------------------------------------------------------------------
class Course(Model):
    id: int
    owner_user_id: int
    title: str
    status: CourseStatus
    syllabus_file: str | None = None
    syllabus_pages: int | None = None
    topic_count: int
    enrolled_count: int


class StudentProgressRow(Model):
    user_id: int
    full_name: str
    enrollment_status: EnrollmentStatus
    completed_topics: int
    total_topics: int
    current_topic: str | None
    last_score: float | None
    has_badge: bool


class PathDashboard(Model):
    course_id: int
    learning_path_id: int
    path_title: str
    group: str
    settings: PathSettings
    enrolled: int
    completion_rate: float
    badges_issued: int
    attempts_per_topic: float
    students: tuple[StudentProgressRow, ...]


class AttemptRecord(Model):
    topic_title: str
    attempt_number: int
    score: float
    passed: bool
    taken_on: date


class StudentDetail(Model):
    user: User
    course_id: int
    path_title: str
    group: str
    enrollment_status: EnrollmentStatus
    profile_description: str | None
    personal_objective: str | None
    levels: tuple[TopicLevel, ...]
    attempts: tuple[AttemptRecord, ...]


class ContentResource(Model):
    id: int
    topic_id: int
    label: str
    sources: str
    faithfulness: float | None
    status: ReviewStatus


class BankQuestion(Model):
    id: int
    topic_id: int
    prompt: str
    bloom_level: BloomLevel
    kind: QuestionKind
    status: ReviewStatus


# --- administración ----------------------------------------------------------------------------
class LlmCall(Model):
    task: str
    model: str
    prompt_version: str
    tokens: int
    cost_usd: float
    latency_seconds: float


class LlmLog(Model):
    period_days: int
    calls: int
    total_cost_usd: float
    p95_latency_seconds: float
    invalid_json_rate: float
    recent: tuple[LlmCall, ...]


class EvaluationMetric(Model):
    key: str
    label: str
    value: float
    target: float | None
    comparison: Literal["gte", "lte", "report"]
    unit: Literal["ratio", "score", "count", "usd"]
