"""B-064: the precise query and the broad fallback with the course as context."""

from app.application.video.service import search_texts
from app.ports.catalog import TopicRecord


def _topic(name: str, course: str, subtopics: list[str] | None = None) -> TopicRecord:
    return TopicRecord(
        id="1",
        course_id=1,
        name=name,
        description="",
        subtopics=subtopics or ["Primer subtema", "Segundo subtema", "Tercero"],
        course_name=course,
    )


def test_the_fallback_adds_the_course_to_a_generic_topic_name() -> None:
    queries = search_texts(_topic("Fundamentos e instalación", "Curso de Claude Code"))
    assert queries == [
        "Fundamentos e instalación Primer subtema Segundo subtema",
        "Fundamentos e instalación Curso de Claude Code",
    ]


def test_the_course_name_is_cut_at_its_subtitle() -> None:
    queries = search_texts(_topic("Fundamentos de MLOps", "Machine Learning Operations - Grupo 2"))
    assert queries[1] == "Fundamentos de MLOps Machine Learning Operations"


def test_without_course_or_when_the_name_has_it_the_fallback_is_the_name() -> None:
    assert search_texts(_topic("Fundamentos de MLOps", ""))[1] == "Fundamentos de MLOps"
    assert search_texts(_topic("Intro a Claude Code", "Claude Code"))[1] == "Intro a Claude Code"


def test_a_topic_without_subtopics_makes_one_query() -> None:
    topic = TopicRecord(id="1", course_id=1, name="Regresión", description="", subtopics=[])
    assert search_texts(topic) == ["Regresión"]
