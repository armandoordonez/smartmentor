"""Páginas de la interfaz, menú superior por rol y destino de cada `next_action`.

`PAGES` lista **todas** las páginas previstas (sección 4 de `app/CLAUDE.md`), con su archivo, su
título y, si la hay, su entrada en el menú de un rol. Solo se registran las que **existen en
disco**: quien construya una pantalla nueva solo crea su archivo en `pages/<área>/` y aparece
sola (y en el menú, si corresponde), sin editar este módulo.

Todas las páginas se registran para todos los roles: el menú solo muestra las del rol activo, pero
si alguien abre otra por URL la API responde 403 y se ve la pantalla A6. La interfaz oculta; la API
protege.
"""

from dataclasses import dataclass
from pathlib import Path

import streamlit as st
from streamlit.navigation.page import StreamlitPage

from clients.models import NextAction, Role

SRC_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class PageSpec:
    path: str
    """Archivo de la página, relativo a `src/`."""
    title: str
    url_path: str
    menu_role: Role | None = None
    """Rol en cuyo menú superior aparece la página."""
    menu_label: str | None = None
    """Texto del enlace del menú (por omisión, el título)."""

    @property
    def exists(self) -> bool:
        return (SRC_DIR / self.path).is_file()


# Comunes
DEMO_ROLE_SELECTOR = "pages/common/demo_role_selector.py"
CONSENT = "pages/common/consent.py"
DATA_RIGHTS = "pages/common/data_rights.py"
COMING_SOON = "pages/common/coming_soon.py"
# Aprendiz
CATALOG = "pages/learner/catalog.py"
ONBOARDING_PROFILE = "pages/learner/onboarding_profile.py"
ONBOARDING_RESUME = "pages/learner/onboarding_resume.py"
MY_PROFILE = "pages/learner/my_profile.py"
# Instructor
COURSES = "pages/instructor/courses.py"
# Administrador
USERS = "pages/admin/users.py"

PAGES: tuple[PageSpec, ...] = (
    # --- Comunes ---
    PageSpec(DEMO_ROLE_SELECTOR, "Entrar", "enter"),
    PageSpec(CONSENT, "Autorizaciones", "consent"),
    PageSpec(DATA_RIGHTS, "Tus datos y tus derechos", "data-rights"),
    PageSpec(COMING_SOON, "Próximamente", "coming-soon"),
    # --- Aprendiz (E, U) ---
    PageSpec(CATALOG, "Rutas", "catalog", "learner", "Rutas"),
    PageSpec(ONBOARDING_PROFILE, "Perfil", "onboarding-profile"),
    PageSpec(ONBOARDING_RESUME, "Hoja de vida", "onboarding-resume"),
    PageSpec("pages/learner/diagnostic.py", "Diagnóstico", "diagnostic"),
    PageSpec(
        "pages/learner/diagnostic_result.py", "Resultado del diagnóstico", "diagnostic-result"
    ),
    PageSpec("pages/learner/path.py", "Vista de ruta", "path"),
    PageSpec("pages/learner/topic.py", "Tema", "topic"),
    PageSpec("pages/learner/quiz.py", "Quiz del tema", "quiz"),
    PageSpec("pages/learner/quiz_result.py", "Resultado del quiz", "quiz-result"),
    PageSpec("pages/learner/final_assessment.py", "Evaluación final", "final-assessment"),
    PageSpec("pages/learner/final_result.py", "Repaso dirigido", "final-result"),
    PageSpec("pages/learner/badge.py", "Badge", "badge"),
    PageSpec("pages/learner/progress.py", "Mi progreso", "progress", "learner", "Mi progreso"),
    PageSpec("pages/learner/achievements.py", "Logros", "achievements", "learner", "Logros"),
    PageSpec("pages/learner/final_survey.py", "Encuesta final", "final-survey"),
    PageSpec("pages/learner/retention_test.py", "Prueba de retención", "retention-test"),
    PageSpec(MY_PROFILE, "Mi perfil", "my-profile", "learner", "Mi perfil"),
    # --- Instructor (D) ---
    PageSpec(COURSES, "Mis cursos", "courses", "instructor", "Cursos"),
    PageSpec("pages/instructor/new_course.py", "Nuevo curso", "new-course"),
    PageSpec("pages/instructor/syllabus_review.py", "Curso y syllabus", "syllabus"),
    PageSpec(
        "pages/instructor/path_dashboard.py",
        "Ruta y avance",
        "path-dashboard",
        "instructor",
        "Rutas y avance",
    ),
    PageSpec("pages/instructor/learner_detail.py", "Detalle de aprendiz", "learner-detail"),
    PageSpec("pages/instructor/content_review.py", "Revisión de contenido", "content-review"),
    PageSpec("pages/instructor/item_annotation.py", "Anotación de preguntas", "item-annotation"),
    PageSpec(
        "pages/instructor/short_answer_grading.py", "Calificación humana", "short-answer-grading"
    ),
    PageSpec("pages/instructor/topic_videos.py", "Video del tema", "topic-videos"),
    PageSpec("pages/instructor/video_quality.py", "Calidad de los videos", "video-quality"),
    # --- Administrador (AD, C4) ---
    PageSpec(USERS, "Usuarios y roles", "users", "admin", "Usuarios"),
    PageSpec("pages/admin/llm_logs.py", "Log LLM y costos", "llm-logs", "admin", "Log LLM"),
    PageSpec("pages/admin/metrics.py", "Métricas globales", "metrics", "admin", "Métricas"),
    PageSpec("pages/admin/pilot.py", "Piloto", "pilot"),
    PageSpec("pages/admin/courses_enrollments.py", "Cursos e inscripciones", "courses-enrollments"),
    PageSpec("pages/admin/prompt_catalog.py", "Catálogo de prompts", "prompt-catalog"),
)

# Página de inicio de cada rol: la primera que exista; si ninguna, «Próximamente».
HOME_CANDIDATES: dict[Role, tuple[str, ...]] = {
    "learner": (CATALOG,),
    "instructor": (COURSES,),
    "admin": (USERS,),
}

# Pantalla de Figma (campo `screen` de `next_action`) -> archivo de la página que la muestra.
SCREEN_PAGES: dict[str, str] = {
    "E1": CATALOG,
    "E2": ONBOARDING_PROFILE,
    "E2b": ONBOARDING_RESUME,
    "E3": "pages/learner/diagnostic.py",
    "U1a": "pages/learner/diagnostic.py",
    "E4": "pages/learner/diagnostic_result.py",
    "E4b": "pages/learner/diagnostic_result.py",
    "E5": "pages/learner/path.py",
    "E5b": "pages/learner/path.py",
    "E6": "pages/learner/topic.py",
    "E6b": "pages/learner/quiz.py",
    "E6c": "pages/learner/quiz.py",
    "U1b": "pages/learner/quiz.py",
    "U1c": "pages/learner/quiz.py",
    "E7": "pages/learner/quiz_result.py",
    "E7b": "pages/learner/quiz_result.py",
    "E7c": "pages/learner/quiz_result.py",
    "E8": "pages/learner/final_assessment.py",
    "U1d": "pages/learner/final_assessment.py",
    "E9": "pages/learner/final_result.py",
    "E9c": "pages/learner/final_result.py",
    "E10": "pages/learner/badge.py",
    "E11": "pages/learner/progress.py",
    "E12": "pages/learner/achievements.py",
    "E13a": "pages/learner/final_survey.py",
    "E13b": "pages/learner/final_survey.py",
    "E14": "pages/learner/retention_test.py",
    "E15": MY_PROFILE,
}


def registered_pages() -> list[PageSpec]:
    """Páginas previstas cuyo archivo existe."""
    return [spec for spec in PAGES if spec.exists]


def is_registered(path: str) -> bool:
    return any(spec.path == path for spec in registered_pages())


def home_for(role: Role) -> str:
    """Archivo de la página de inicio del rol, o «Próximamente» si todavía no se construye."""
    for path in HOME_CANDIDATES[role]:
        if is_registered(path):
            return path
    return COMING_SOON


def menu_links(role: Role) -> list[tuple[str, str]]:
    """(archivo, texto) de los enlaces del menú superior del rol, en el orden de `PAGES`."""
    return [
        (spec.path, spec.menu_label or spec.title)
        for spec in registered_pages()
        if spec.menu_role == role
    ]


def page_for_next_action(action: NextAction) -> str | None:
    """Página que atiende un `next_action`, o None si todavía no existe.

    La app navega por lo que dice la API; nunca deduce el estado. El mapa va de `screen` a página.
    """
    if action.screen is None:
        return None
    path = SCREEN_PAGES.get(action.screen)
    return path if path is not None and is_registered(path) else None


def build_navigation(
    role: Role | None, *, authenticated: bool, consent_only: bool = False
) -> StreamlitPage:
    """Registra las páginas existentes y devuelve la que se debe mostrar.

    Sin sesión solo existe el selector de rol del modo `fixtures`. Con `consent_only` (falta la
    autorización de datos, CU-34) solo se registran las pantallas de consentimiento.
    """
    if not authenticated or role is None:
        selector = st.Page(DEMO_ROLE_SELECTOR, title="Entrar", url_path="enter", default=True)
        return st.navigation([selector], position="hidden")
    if consent_only:
        return st.navigation(
            [
                st.Page(CONSENT, title="Autorizaciones", url_path="consent", default=True),
                st.Page(DATA_RIGHTS, title="Tus datos y tus derechos", url_path="data-rights"),
            ],
            position="hidden",
        )
    home = home_for(role)
    pages = [
        st.Page(spec.path, title=spec.title, url_path=spec.url_path, default=spec.path == home)
        for spec in registered_pages()
        if spec.path != DEMO_ROLE_SELECTOR
    ]
    return st.navigation(pages, position="hidden")
