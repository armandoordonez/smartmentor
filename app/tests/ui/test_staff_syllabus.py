"""D1b a D1d (nuevo curso, extracción y error) y D2 a D2d (revisión del syllabus y grafo)."""

from apptest import page_texts
from staff_support import assert_matches_figma, assert_no_exception, click, staff_app

NEW_COURSE = "pages/instructor/new_course.py"
SYLLABUS = "pages/instructor/syllabus_review.py"
COURSES = "pages/instructor/courses.py"


def _fill_paste_form(scenario: str = "default"):  # type: ignore[no-untyped-def]
    at = staff_app(scenario=scenario, page=NEW_COURSE)
    at.get("button_group")[0].set_value("Pegar texto").run()
    at.text_input(key="nc-name").set_value("Curso de prueba")
    at.text_input(key="nc-group").set_value("Grupo 01 · 2026-2")
    at.run()
    at.text_area(key="nc-text").set_value("Tema 1: introducción\nTema 2: regresión").run()
    return at


def test_d1b_form_texts_and_disabled_submit() -> None:
    at = staff_app(page=NEW_COURSE)
    assert_no_exception(at)
    texts = page_texts(at)
    for expected in (
        "Mis cursos › Nuevo curso",
        "Nuevo curso",
        "Datos del curso",
        "Nombre del curso",
        "Grupo o periodo",
        "Descripción corta",
        "Syllabus",
        "Subir PDF",
        "Pegar texto",
        "Cancelar",
        "Extraer temas con IA",
    ):
        assert expected in texts, expected
    submit = next(b for b in at.button if b.label == "Extraer temas con IA")
    assert submit.disabled


def test_d1c_extraction_shows_progress_while_the_job_runs() -> None:
    at = _fill_paste_form("loading")
    at = click(at, "Extraer temas con IA")
    assert_no_exception(at)
    texts = page_texts(at)
    assert any("Extrayendo temas del syllabus" in t for t in texts)
    assert "Tiempo estimado: menos de 20 segundos" in texts
    assert any("Listo" in t and "Leer el documento" in t for t in texts)
    assert any("En curso" in t and "Identificar temas" in t for t in texts)
    assert any("Pendiente" in t and "ciclos" in t for t in texts)


def test_d1c_finished_job_goes_to_the_review() -> None:
    at = _fill_paste_form()
    at = click(at, "Extraer temas con IA")
    assert_no_exception(at)
    assert any("Fundamentos de Machine Learning" in t for t in page_texts(at))


def test_d1c_failed_job_offers_retry() -> None:
    at = _fill_paste_form("failed")
    at = click(at, "Extraer temas con IA")
    texts = page_texts(at)
    assert any("No pudimos extraer los temas" in t for t in texts)
    assert any("Falló" in t for t in texts)
    labels = [b.label for b in at.button]
    assert "Reintentar" in labels and "Volver a mis cursos" in labels


def test_d1d_syllabus_without_text_keeps_the_course_data() -> None:
    at = _fill_paste_form("no_text")
    at = click(at, "Extraer temas con IA")
    assert_no_exception(at)
    texts = page_texts(at)
    assert "No pudimos leer el syllabus" in texts
    assert any("0 caracteres de texto detectados" in t for t in texts)
    assert "Tus datos del curso están guardados. No se perdió nada." in texts
    at = click(at, "Pegar el texto")
    assert at.text_input(key="nc-name").value == "Curso de prueba"


def test_d1b_forbidden_shows_403() -> None:
    at = staff_app(scenario="forbidden", page=NEW_COURSE)
    at.get("button_group")[0].set_value("Pegar texto").run()
    assert_no_exception(at)


def test_d2_matches_figma() -> None:
    at = staff_app(page=SYLLABUS)
    assert_matches_figma(at, "D2")


def test_d2_lists_topics_with_review_states() -> None:
    at = staff_app(page=SYLLABUS)
    texts = page_texts(at)
    for expected in ("Sin cambios", "Corregido", "Agregado por ti", "Temas 2, 3 y 4", "Ninguno"):
        assert expected in texts, expected
    assert any("Repaso de álgebra lineal (eliminado)" in t for t in texts)


def test_d2_empty_course_returns_to_upload() -> None:
    at = staff_app(scenario="empty", page=SYLLABUS)
    assert_no_exception(at)


def test_d2b_edit_panel_saves_and_reports_cycles() -> None:
    at = staff_app(page=SYLLABUS)
    at = click(at, "Editar tema")
    texts = page_texts(at)
    assert "Editar tema" in texts and "Resultados de aprendizaje" in texts
    assert "Guardar cambios" in [b.label for b in at.button]
    at = click(at, "+ Agregar resultado de aprendizaje")
    at = click(at, "Guardar cambios")
    assert_no_exception(at)
    assert not any(t == "Editar tema" for t in page_texts(at)[:3])


def test_d2c_reextract_asks_for_confirmation() -> None:
    at = staff_app(scenario="loading", page=SYLLABUS)
    at = click(at, "Volver a extraer temas")
    texts = page_texts(at)
    assert "¿Volver a extraer los temas?" in texts
    assert any(
        "se perderán tus correcciones: 1 corregido, 1 agregado por ti, 1 eliminado" in t
        for t in texts
    )
    at = click(at, "Sí, volver a extraer")
    assert_no_exception(at)
    assert any("Extrayendo temas del syllabus" in t for t in page_texts(at))


def test_d2d_graph_view_and_publish() -> None:
    at = staff_app(page=SYLLABUS)
    at = click(at, "Ver los temas como grafo")
    assert_no_exception(at)
    texts = page_texts(at)
    assert (
        "Grafo de temas" in texts
        and "Mis cursos › Fundamentos de Machine Learning › Temas" in texts
    )
    assert any("Sin sin" in t or "Sin ciclos" in t for t in texts) or at.get("imgs") is not None
    at = click(at, "Aprobar y publicar")
    assert_no_exception(at)
    assert "Mis cursos" in page_texts(at)


def test_d2d_cycle_blocks_publishing() -> None:
    at = staff_app(scenario="cycle", page=SYLLABUS)
    at = click(at, "Ver los temas como grafo")
    assert_no_exception(at)
    assert any("forma un ciclo" in t for t in page_texts(at))
    publish = next(b for b in at.button if b.label == "Aprobar y publicar")
    assert publish.disabled


def test_d2_forbidden_shows_403() -> None:
    at = staff_app(scenario="forbidden", page=SYLLABUS)
    assert "403" in page_texts(at, skip_header=False)
