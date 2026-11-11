"""D1 · Mis cursos."""

from apptest import page_texts
from staff_support import (
    assert_matches_figma,
    assert_no_exception,
    staff_app,
    staff_text_reader,  # noqa: F401
)
from streamlit.testing.v1 import AppTest

COURSES = "pages/instructor/courses.py"


def test_d1_matches_figma() -> None:
    at = staff_app(page=COURSES)
    assert_matches_figma(
        at,
        "D1",
        # El nombre del usuario es la barra superior (avatar); las tres acciones son botones.
        accepted=("Prof. Elena Ramírez", *["Syllabus · Ruta · Recursos"] * 6),
    )


def test_d1_empty_state() -> None:
    at = staff_app(scenario="empty", page=COURSES)
    assert_no_exception(at)
    assert any("Todavía no tienes cursos" in t for t in page_texts(at))


def test_d1_forbidden_shows_403() -> None:
    at = staff_app(scenario="forbidden", page=COURSES)
    assert_no_exception(at)
    assert "403" in page_texts(at, skip_header=False)


def test_d1_service_error_is_a_warning_not_a_crash() -> None:
    at = staff_app(scenario="error", page=COURSES)
    assert_no_exception(at)
    assert at.error or any("servicio" in t.lower() for t in page_texts(at, skip_header=False))


def test_d1_new_course_button_is_there() -> None:
    at = staff_app(page=COURSES)
    assert "Nuevo curso" in [b.label for b in at.button]


def _keys(at: AppTest) -> set[str]:
    return {b.key for b in at.button if b.key}


def test_d1_only_draft_or_published_courses_offer_archive() -> None:
    at = staff_app(page=COURSES)
    keys = _keys(at)
    assert "courses-2-archive" in keys  # publicado
    assert "courses-3-archive" in keys  # borrador
    assert "courses-1-archive" not in keys  # en revisión


def test_d1_archive_asks_first_and_cancel_keeps_the_course() -> None:
    at = staff_app(page=COURSES)
    at.button(key="courses-2-archive").click().run()
    assert_no_exception(at)
    assert any("¿Archivar «Python para análisis de datos»?" in t for t in page_texts(at))
    at.button(key="archive-no").click().run()
    assert not any("¿Archivar" in t for t in page_texts(at))
    assert any("Python para análisis de datos" in t for t in page_texts(at))


def test_d1_archived_course_leaves_the_list_and_can_be_shown_again() -> None:
    at = staff_app(page=COURSES)
    at.button(key="courses-2-archive").click().run()
    at.button(key="archive-yes").click().run()
    assert_no_exception(at)
    assert any("Archivaste «Python para análisis de datos»" in s.value for s in at.success)
    assert "courses-2-syllabus" not in _keys(at)  # la fila ya no está

    toggle = at.toggle(key="courses-show-archived")
    assert toggle.label == "Ver cursos archivados (1)"
    toggle.set_value(True).run()
    assert "courses-2-syllabus" in _keys(at)
    assert "courses-2-archive" not in _keys(at)  # archivado: no se vuelve a ofrecer
