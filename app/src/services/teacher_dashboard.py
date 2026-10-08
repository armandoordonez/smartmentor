"""Pantallas del docente: cursos (D1), syllabus (D2), ruta y avance (D3), detalle de un estudiante
(D4) y revisión del contenido generado con IA (D5).

La API solo devuelve los cursos del docente y los estudiantes inscritos en sus rutas; la interfaz
no filtra por su cuenta.
"""

from clients.base import SmartMentorClient
from clients.models import (
    BankQuestion,
    ContentResource,
    Course,
    PathDashboard,
    PathSettings,
    ReviewStatus,
    StudentDetail,
    Topic,
    User,
)


class TeacherService:
    def __init__(self, client: SmartMentorClient) -> None:
        self._client = client

    def me(self) -> User:
        return self._client.me()

    def courses(self) -> list[Course]:
        return self._client.list_my_courses()

    def create_course(self, title: str) -> Course:
        return self._client.create_course(title)

    def course(self, course_id: int) -> Course:
        return self._client.get_course(course_id)

    def topics(self, course_id: int) -> list[Topic]:
        self._client.get_course(course_id)
        return self._client.list_topics(course_id)

    def publish(self, course_id: int) -> Course:
        return self._client.publish_course(course_id)

    def dashboard(self, course_id: int) -> PathDashboard:
        return self._client.get_path_dashboard(course_id)

    def update_settings(self, course_id: int, settings: PathSettings) -> PathSettings:
        return self._client.update_path_settings(course_id, settings)

    def student_detail(self, course_id: int, user_id: int) -> StudentDetail:
        return self._client.get_student_detail(course_id, user_id)

    def resources(self, topic_id: int) -> list[ContentResource]:
        return self._client.list_topic_resources(topic_id)

    def questions(self, topic_id: int) -> list[BankQuestion]:
        return self._client.list_topic_questions(topic_id)

    def set_resource_status(self, resource_id: int, status: ReviewStatus) -> ContentResource:
        return self._client.set_resource_status(resource_id, status)

    def set_question_status(self, question_id: int, status: ReviewStatus) -> BankQuestion:
        return self._client.set_question_status(question_id, status)
