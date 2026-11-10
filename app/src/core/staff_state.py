"""Estado de la sesión de las páginas del instructor y del administrador.

Todo vive en `st.session_state` (por sesión), nunca en cachés compartidas. Las páginas se pasan el
curso, la ruta, la inscripción y el tema elegidos por aquí; la API autoriza cada llamada.
"""

import uuid
from dataclasses import dataclass

import streamlit as st

from core.session import get_session

_KEY = "staff_state"

# Páginas del instructor y del administrador (archivos de `src/`).
COURSES = "pages/instructor/courses.py"
NEW_COURSE = "pages/instructor/new_course.py"
SYLLABUS_REVIEW = "pages/instructor/syllabus_review.py"
PATH_DASHBOARD = "pages/instructor/path_dashboard.py"
LEARNER_DETAIL = "pages/instructor/learner_detail.py"
CONTENT_REVIEW = "pages/instructor/content_review.py"
ITEM_ANNOTATION = "pages/instructor/item_annotation.py"
SHORT_ANSWER_GRADING = "pages/instructor/short_answer_grading.py"
TOPIC_VIDEOS = "pages/instructor/topic_videos.py"
VIDEO_QUALITY = "pages/instructor/video_quality.py"
LLM_LOGS = "pages/admin/llm_logs.py"
PILOT = "pages/admin/pilot.py"
COURSES_ENROLLMENTS = "pages/admin/courses_enrollments.py"
PROMPT_CATALOG = "pages/admin/prompt_catalog.py"
USERS = "pages/admin/users.py"
METRICS = "pages/admin/metrics.py"

DEFAULT_PILOT_ID = 1
"""El contrato no lista pilotos (`GET /pilots/{id}` solo); hay un piloto por cohorte."""


@dataclass
class StaffState:
    course_id: int | None = None
    path_id: int | None = None
    enrollment_id: int | None = None
    topic_id: int | None = None
    job_id: str | None = None
    flash: str | None = None


def get_staff_state() -> StaffState:
    if _KEY not in st.session_state:
        st.session_state[_KEY] = StaffState()
    state: StaffState = st.session_state[_KEY]
    return state


def idempotency_key(operation: str) -> str:
    """Clave estable por operación entre reejecuciones; `forget_key` la renueva tras un éxito."""
    keys = get_session().idempotency_keys
    if operation not in keys:
        keys[operation] = str(uuid.uuid4())
    return keys[operation]


def forget_key(operation: str) -> None:
    get_session().idempotency_keys.pop(operation, None)


def pop_flash() -> str | None:
    state = get_staff_state()
    message, state.flash = state.flash, None
    return message
