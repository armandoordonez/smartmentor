"""Contrato del acceso a datos de la interfaz.

`SmartMentorClient` lista las operaciones que usan las pantallas. Lo implementan los datos de
ejemplo (`sample_data.py`) y, cuando exista el login, el cliente HTTP de la API. Las pantallas y
los servicios solo dependen de este Protocol, así que cambiar de fuente no las toca.
"""

from typing import Protocol

from clients.models import (
    Badge,
    BankQuestion,
    ContentResource,
    Course,
    Diagnostic,
    Enrollment,
    EvaluationMetric,
    FinalAssessment,
    FinalResult,
    LearningPath,
    LlmLog,
    PathDashboard,
    PathProgress,
    PathSettings,
    Quiz,
    QuizResult,
    ReviewStatus,
    Role,
    StudentDetail,
    Topic,
    TopicContent,
    User,
)

Answers = dict[int, int | None]
"""Respuestas por id de pregunta: índice de la opción elegida o None («No lo sé»)."""


class ApiError(Exception):
    """Error de la API con su código (las respuestas RFC 9457 traen `status` y `code`)."""

    def __init__(self, status: int, code: str, detail: str = "") -> None:
        super().__init__(f"{status} {code}: {detail}")
        self.status = status
        self.code = code
        self.detail = detail


class SmartMentorClient(Protocol):
    # --- identidad -----------------------------------------------------------------------------
    def me(self) -> User: ...

    # --- catálogo ------------------------------------------------------------------------------
    def list_learning_paths(self) -> list[LearningPath]: ...

    def get_learning_path(self, learning_path_id: int) -> LearningPath: ...

    def list_topics(self, course_id: int) -> list[Topic]: ...

    # --- estudiante ----------------------------------------------------------------------------
    def list_my_enrollments(self) -> list[Enrollment]: ...

    def enroll(self, learning_path_id: int, profile_description: str) -> Enrollment: ...

    def get_diagnostic(self, enrollment_id: int) -> Diagnostic: ...

    def submit_diagnostic(self, enrollment_id: int, answers: Answers) -> Diagnostic: ...

    def confirm_objective(self, enrollment_id: int, personal_objective: str) -> Enrollment: ...

    def get_path_progress(self, enrollment_id: int) -> PathProgress: ...

    def get_topic_content(self, topic_id: int) -> TopicContent: ...

    def get_topic_quiz(self, enrollment_id: int, topic_id: int) -> Quiz: ...

    def submit_topic_quiz(
        self, enrollment_id: int, topic_id: int, answers: Answers
    ) -> QuizResult: ...

    def get_final_assessment(self, enrollment_id: int) -> FinalAssessment: ...

    def submit_final_assessment(self, enrollment_id: int, answers: Answers) -> FinalResult: ...

    def list_final_results(self, enrollment_id: int) -> list[FinalResult]: ...

    def list_my_badges(self) -> list[Badge]: ...

    # --- docente -------------------------------------------------------------------------------
    def list_my_courses(self) -> list[Course]: ...

    def create_course(self, title: str) -> Course: ...

    def get_course(self, course_id: int) -> Course: ...

    def publish_course(self, course_id: int) -> Course: ...

    def get_path_dashboard(self, course_id: int) -> PathDashboard: ...

    def update_path_settings(self, course_id: int, settings: PathSettings) -> PathSettings: ...

    def get_student_detail(self, course_id: int, user_id: int) -> StudentDetail: ...

    def list_topic_resources(self, topic_id: int) -> list[ContentResource]: ...

    def list_topic_questions(self, topic_id: int) -> list[BankQuestion]: ...

    def set_resource_status(self, resource_id: int, status: ReviewStatus) -> ContentResource: ...

    def set_question_status(self, question_id: int, status: ReviewStatus) -> BankQuestion: ...

    # --- administración ------------------------------------------------------------------------
    def list_users(self) -> list[User]: ...

    def create_user(self, full_name: str, email: str, role: Role) -> User: ...

    def set_user_role(self, user_id: int, role: Role) -> User: ...

    def set_user_active(self, user_id: int, active: bool) -> User: ...

    def get_llm_log(self) -> LlmLog: ...

    def list_evaluation_metrics(self) -> list[EvaluationMetric]: ...
