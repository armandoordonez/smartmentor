"""B-064: el texto que explica por qué un tema tiene pocos videos."""

from clients.models_staff import VideoSearch
from services.staff_content import video_search_text


def _search(**fields: object) -> VideoSearch:
    return VideoSearch.model_validate({"job_id": "j", "status": "succeeded", **fields})


def test_with_three_or_more_videos_there_is_nothing_to_say() -> None:
    assert video_search_text(_search(found=20, excluded={}), 3) is None
    assert video_search_text(None, 5) is None


def test_a_running_search_is_announced_even_with_videos() -> None:
    assert video_search_text(_search(status="running"), 4) == "Buscando videos en YouTube…"


def test_a_search_before_b064_asks_to_search_again() -> None:
    text = video_search_text(_search(), 0)
    assert text is not None and text.startswith("La última búsqueda es anterior a este resumen.")


def test_youtube_returned_nothing() -> None:
    assert video_search_text(_search(found=0), 0) == (
        "YouTube no devolvió videos para este tema. Puedes agregar uno a mano."
    )


def test_without_a_youtube_key_nothing_was_searched() -> None:
    text = video_search_text(_search(found=0, queries=[]), 0)
    assert text is not None and text.startswith("No se buscó en YouTube")
    assert "YOUTUBE_API_KEY" in text


def test_youtube_returned_nothing_after_the_broad_query_too() -> None:
    search = _search(found=0, queries=["Tema subtema", "Tema Curso"])
    assert video_search_text(search, 0) == (
        "YouTube no devolvió videos para este tema. Puedes agregar uno a mano."
    )


def test_few_results_without_exclusions() -> None:
    assert video_search_text(_search(found=2, excluded={}), 2) == (
        "YouTube solo devolvió 2 videos para este tema."
    )


def test_one_video_dropped_by_language_uses_the_singular() -> None:
    assert video_search_text(_search(found=1, excluded={"language_not_understood": 1}), 0) == (
        "YouTube devolvió 1 video; quedaron fuera 1 por idioma."
    )


def test_another_failure_shows_its_code() -> None:
    failed = _search(status="failed", error_code="BUDGET_EXCEEDED")
    assert video_search_text(failed, 0) == "La última búsqueda falló (BUDGET_EXCEEDED)."
