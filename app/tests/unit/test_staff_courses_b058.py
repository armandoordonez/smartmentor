"""B-058: «Rutas y avance» abre la ruta activa más reciente, nunca una archivada."""

from typing import Any

from clients.models import LearningPathRef, Page
from clients.models_staff import Course
from services.staff_courses import first_path_id


def _course(course_id: int, status: str, path_id: int | None) -> Course:
    path = LearningPathRef(id=path_id, name=f"Ruta {path_id}") if path_id is not None else None
    return Course(id=course_id, name=f"Curso {course_id}", status=status, learning_path=path)  # type: ignore[arg-type]


class _Client:
    def __init__(self, courses: list[Course]) -> None:
        self._courses = courses

    def list_courses(self, **_: Any) -> Page[Course]:
        return Page[Course](items=self._courses, total=len(self._courses), limit=50, offset=0)


def _pick(*courses: Course) -> int | None:
    return first_path_id(_Client(list(courses)))  # type: ignore[arg-type]


def test_skips_the_archived_first_course() -> None:
    assert _pick(_course(1, "archived", 1), _course(2, "published", 2)) == 2


def test_prefers_the_most_recent_published_path() -> None:
    assert (
        _pick(_course(2, "published", 2), _course(5, "published", 5), _course(3, "published", 3))
        == 5
    )


def test_prefers_published_over_a_newer_course_in_review() -> None:
    assert _pick(_course(2, "published", 2), _course(7, "in_review", 7)) == 2


def test_falls_back_to_a_course_in_preparation() -> None:
    assert _pick(_course(1, "archived", 1), _course(4, "in_review", 4)) == 4


def test_none_when_every_course_is_archived_or_has_no_path() -> None:
    assert _pick(_course(1, "archived", 1), _course(2, "draft", None)) is None
