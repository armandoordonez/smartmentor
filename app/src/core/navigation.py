"""Páginas de la interfaz y enlaces de la barra superior según el rol.

Todas las páginas se registran para todos los roles: el menú solo muestra las del rol, pero si
alguien abre otra por URL, la API (o los datos de ejemplo) responde 403 y se ve la pantalla A6.
La interfaz oculta; la API protege.
"""

from dataclasses import dataclass

import streamlit as st
from streamlit.navigation.page import StreamlitPage

from clients.models import Role

# Estudiante
CATALOG = "pages/student/catalog.py"
DIAGNOSTIC = "pages/student/diagnostic.py"
MY_PATH = "pages/student/my_path.py"
TOPIC = "pages/student/topic.py"
FINAL_ASSESSMENT = "pages/student/final_assessment.py"
REVIEW = "pages/student/review.py"
BADGE = "pages/student/badge.py"
PROGRESS = "pages/student/progress.py"
ACHIEVEMENTS = "pages/student/achievements.py"
# Docente
COURSES = "pages/teacher/courses.py"
SYLLABUS = "pages/teacher/syllabus_review.py"
DASHBOARD = "pages/teacher/dashboard.py"
STUDENT_DETAIL = "pages/teacher/student_detail.py"
CONTENT_REVIEW = "pages/teacher/content_review.py"
# Administración
USERS = "pages/admin/users.py"
LLM_LOGS = "pages/admin/llm_logs.py"
METRICS = "pages/admin/metrics.py"
# Entrada sin login (solo con datos de ejemplo)
ROLE_SELECTOR = "pages/common/role_selector.py"


@dataclass(frozen=True)
class PageSpec:
    path: str
    title: str
    url_path: str


PAGES = (
    PageSpec(CATALOG, "Rutas", "catalog"),
    PageSpec(DIAGNOSTIC, "Diagnóstico", "diagnostic"),
    PageSpec(MY_PATH, "Mi ruta", "my-path"),
    PageSpec(TOPIC, "Tema", "topic"),
    PageSpec(FINAL_ASSESSMENT, "Evaluación final", "final-assessment"),
    PageSpec(REVIEW, "Repaso dirigido", "review"),
    PageSpec(BADGE, "Badge", "badge"),
    PageSpec(PROGRESS, "Mi progreso", "progress"),
    PageSpec(ACHIEVEMENTS, "Logros", "achievements"),
    PageSpec(COURSES, "Mis cursos", "courses"),
    PageSpec(SYLLABUS, "Curso y syllabus", "syllabus"),
    PageSpec(DASHBOARD, "Ruta y avance", "path-dashboard"),
    PageSpec(STUDENT_DETAIL, "Detalle de estudiante", "student-detail"),
    PageSpec(CONTENT_REVIEW, "Revisión de contenido", "content-review"),
    PageSpec(USERS, "Usuarios y roles", "users"),
    PageSpec(LLM_LOGS, "Log LLM y costos", "llm-log"),
    PageSpec(METRICS, "Métricas globales", "metrics"),
)

HOME: dict[Role, str] = {"student": CATALOG, "teacher": COURSES, "admin": USERS}

LINKS: dict[Role, tuple[tuple[str, str], ...]] = {
    "student": ((CATALOG, "Rutas"), (PROGRESS, "Mi progreso"), (ACHIEVEMENTS, "Logros")),
    "teacher": ((COURSES, "Cursos"), (DASHBOARD, "Rutas y avance")),
    "admin": ((USERS, "Usuarios"), (LLM_LOGS, "Log LLM"), (METRICS, "Métricas")),
}


def build_navigation(role: Role | None) -> StreamlitPage:
    """Registra las páginas y devuelve la que se debe mostrar. Sin rol, solo el selector."""
    if role is None:
        selector = st.Page(ROLE_SELECTOR, title="Entrar", url_path="enter", default=True)
        return st.navigation([selector], position="hidden")
    pages = [
        st.Page(
            spec.path, title=spec.title, url_path=spec.url_path, default=spec.path == HOME[role]
        )
        for spec in PAGES
    ]
    return st.navigation(pages, position="hidden")
