"""D1 · Mis cursos."""

from apptest import page_texts
from staff_support import (
    assert_matches_figma,
    assert_no_exception,
    staff_app,
    staff_text_reader,  # noqa: F401
)

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
