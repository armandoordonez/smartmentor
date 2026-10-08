"""Estado de la sesión de cada usuario, con sus claves en un solo lugar.

Todo lo personal vive aquí (en `st.session_state`), nunca en cachés compartidas. Las páginas leen
y escriben `AppSession`; los componentes no lo tocan: reciben sus datos por parámetro.
"""

from dataclasses import dataclass, field

import streamlit as st

from clients.base import Answers
from clients.models import QuizResult, Role

_KEY = "app_session"


@dataclass
class AppSession:
    role: Role | None = None
    user_id: int | None = None

    # Estudiante
    selected_path_id: int | None = None
    selected_topic_id: int | None = None
    diagnostic_index: int = 0
    diagnostic_answers: Answers = field(default_factory=dict)
    editing_objective: bool = False
    quiz_topic_id: int | None = None
    quiz_index: int = 0
    quiz_answers: Answers = field(default_factory=dict)
    quiz_result: QuizResult | None = None
    final_index: int = 0
    final_answers: Answers = field(default_factory=dict)

    # Docente
    selected_course_id: int | None = None
    selected_student_id: int | None = None
    review_topic_id: int | None = None

    def start_onboarding(self, path_id: int) -> None:
        self.selected_path_id = path_id
        self.diagnostic_index = 0
        self.diagnostic_answers = {}
        self.editing_objective = False

    def open_topic(self, topic_id: int) -> None:
        """Abre un tema desde otra pantalla: conserva un quiz a medias, no un resultado viejo."""
        self.selected_topic_id = topic_id
        if self.quiz_topic_id != topic_id or self.quiz_result is not None:
            self.reset_quiz(topic_id)

    def reset_quiz(self, topic_id: int | None) -> None:
        self.quiz_topic_id = topic_id
        self.quiz_index = 0
        self.quiz_answers = {}
        self.quiz_result = None

    def reset_final(self) -> None:
        self.final_index = 0
        self.final_answers = {}


def get_session() -> AppSession:
    if _KEY not in st.session_state:
        st.session_state[_KEY] = AppSession()
    session: AppSession = st.session_state[_KEY]
    return session


def start_session(role: Role, user_id: int) -> None:
    st.session_state[_KEY] = AppSession(role=role, user_id=user_id)


def end_session() -> None:
    st.session_state[_KEY] = AppSession()
