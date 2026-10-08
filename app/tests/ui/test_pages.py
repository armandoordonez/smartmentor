"""Pruebas de páginas con streamlit.testing.v1.AppTest sobre los datos de ejemplo."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from clients.models import Role
from core import navigation
from core.session import AppSession

MAIN = str(Path(__file__).resolve().parents[2] / "src" / "main.py")
USER_BY_ROLE: dict[Role, int] = {"student": 1, "teacher": 2, "admin": 3}

# (página, título que debe mostrar con los datos de ejemplo)
STUDENT_PAGES = [
    (navigation.CATALOG, "Rutas"),
    (navigation.MY_PATH, "Fundamentos de Machine Learning"),
    (navigation.TOPIC, "Regresión logística"),
    (navigation.FINAL_ASSESSMENT, "Evaluación final"),
    (navigation.REVIEW, "Repaso dirigido"),
    (navigation.BADGE, "Badge"),
    (navigation.PROGRESS, "Mi progreso"),
    (navigation.ACHIEVEMENTS, "Logros"),
]
TEACHER_PAGES = [
    (navigation.COURSES, "Mis cursos"),
    (navigation.SYLLABUS, "Fundamentos de Machine Learning"),
    (navigation.DASHBOARD, "Fundamentos de Machine Learning · Grupo 2026-2"),
    (navigation.STUDENT_DETAIL, "Laura Martínez"),
    (navigation.CONTENT_REVIEW, "Revisión de contenido generado con IA"),
]
ADMIN_PAGES = [
    (navigation.USERS, "Usuarios y roles"),
    (navigation.LLM_LOGS, "Log LLM y costos"),
    (navigation.METRICS, "Métricas de evaluación"),
]


def app_as(role: Role, page: str, **session: object) -> AppTest:
    at = AppTest.from_file(MAIN, default_timeout=30)
    at.session_state["app_session"] = AppSession(role=role, user_id=USER_BY_ROLE[role], **session)
    # La primera ejecución registra las páginas (con su url_path); solo entonces se puede
    # cambiar a una por su archivo.
    at.run()
    at.switch_page(page)
    return at.run()


def titles(at: AppTest) -> list[str]:
    return [str(t.value) for t in at.title]


def texts(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [t.value for t in at.title]
    parts += [c.value for c in at.caption] + [w.value for w in at.warning]
    parts += [s.value for s in at.subheader] + [i.value for i in at.info]
    return "\n".join(str(p) for p in parts)


def test_without_role_shows_the_role_selector() -> None:
    at = AppTest.from_file(MAIN, default_timeout=30).run()
    assert not at.exception
    assert "¿Cómo quieres entrar?" in texts(at)

    next(b for b in at.button if b.label == "Entrar como estudiante").click()
    at.run()
    assert not at.exception
    assert "Elige una ruta" in texts(at)


@pytest.mark.parametrize(("page", "title"), STUDENT_PAGES)
def test_student_pages_render(page: str, title: str) -> None:
    at = app_as("student", page, selected_path_id=1)
    assert not at.exception, at.exception
    assert title in titles(at)


@pytest.mark.parametrize(("page", "title"), TEACHER_PAGES)
def test_teacher_pages_render(page: str, title: str) -> None:
    at = app_as("teacher", page, selected_course_id=1, selected_student_id=1)
    assert not at.exception, at.exception
    assert title in titles(at)


@pytest.mark.parametrize(("page", "title"), ADMIN_PAGES)
def test_admin_pages_render(page: str, title: str) -> None:
    at = app_as("admin", page)
    assert not at.exception, at.exception
    assert title in titles(at)


def test_student_opening_a_teacher_page_gets_403() -> None:
    at = app_as("student", navigation.COURSES)
    assert not at.exception
    content = texts(at)
    assert "403" in content and "No tienes permiso para ver esta página" in content


def test_path_view_shows_the_design_state() -> None:
    content = texts(app_as("student", navigation.MY_PATH, selected_path_id=1))
    assert "Progreso: 2 de 5 temas · 1 omitido por tu diagnóstico (ahorro 1 h 20 min)" in content
    assert "Intento 2 de 3 · último puntaje 60 %" in content


def test_opening_a_new_path_starts_with_the_profile_step() -> None:
    at = app_as("student", navigation.CATALOG)
    next(b for b in at.button if b.key == "open-path-2").click()
    at.run()
    assert not at.exception
    assert "PASO 1 DE 3 · PERFIL" in texts(at)


def test_answering_the_topic_quiz_shows_the_result() -> None:
    from clients.sample_seed import build_seed

    correct = {q.id: q.correct for q in build_seed().quiz_questions if q.topic_id == 13}
    at = app_as("student", navigation.TOPIC, selected_path_id=1, selected_topic_id=13)
    for _ in range(4):
        question_id = int(at.radio[0].key.rsplit("-", 1)[1])
        at.radio[0].set_value(correct[question_id]).run()
        next(b for b in at.button if b.label in ("Siguiente", "Enviar respuesta")).click()
        at.run()
        if "¡Tema aprobado!" in titles(at):
            break
    assert not at.exception
    assert "¡Tema aprobado!" in titles(at)


def test_final_assessment_demo_leads_to_the_review() -> None:
    from clients.sample_seed import build_seed

    store = build_seed()
    for step in store.steps:
        if step.enrollment_id == 1 and step.status != "skipped":
            step.status, step.attempts_used, step.last_score = "approved", 1, 0.9
    at = AppTest.from_file(MAIN, default_timeout=30)
    at.session_state["sample_store"] = store
    at.session_state["app_session"] = AppSession(role="student", user_id=1, selected_path_id=1)
    at.run()
    at.switch_page(navigation.FINAL_ASSESSMENT).run()
    next(b for b in at.button if "Demo del prototipo" in b.label).click()
    at.run()
    assert not at.exception
    assert "Aún no alcanzas el badge" in titles(at)
    assert "Intento 1 de 3 usado." in texts(at)
