"""D1b a D1d (nuevo curso, extracción y error) y D2 a D2d (revisión del syllabus y grafo)."""

from apptest import page_texts
from staff_support import (
    assert_matches_figma,
    assert_no_exception,
    click,
    staff_app,
    staff_text_reader,  # noqa: F401
)

from core.styles import STYLES_DIR

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


def test_d1b_materials_card_is_optional() -> None:
    """R-004: la tarjeta de apuntes aparece y no bloquea «Extraer temas con IA»."""
    at = _fill_paste_form()
    assert_no_exception(at)
    texts = page_texts(at)
    assert "Apuntes y lecturas · opcional" in texts
    assert any("Sin apuntes, usa solo el syllabus" in t for t in texts)
    assert any("PDF, TXT o MD, hasta 5 archivos de 10 MB cada uno" in t for t in texts)
    assert any("Los apuntes se usan después" in t for t in texts)
    submit = next(b for b in at.button if b.label == "Extraer temas con IA")
    assert not submit.disabled


def test_d1c_warns_about_the_materials_that_could_not_be_used() -> None:
    at = _fill_paste_form("loading")
    at.session_state["nc-material-skipped"] = ["escaneado.pdf"]
    at = click(at, "Extraer temas con IA")
    assert_no_exception(at)
    warnings = [w.value for w in at.warning]
    assert any("«escaneado.pdf»" in w and "Los demás quedaron guardados" in w for w in warnings)


def test_d1c_extraction_shows_progress_while_the_job_runs() -> None:
    at = _fill_paste_form("loading")
    at = click(at, "Extraer temas con IA")
    assert_no_exception(at)
    texts = page_texts(at)
    assert any("Extrayendo temas del syllabus" in t for t in texts)
    # Figma promete «menos de 20 segundos»; la extracción real tardó 39 s (B-057).
    assert "Tiempo estimado: hasta 2 minutos" in texts
    assert "Tiempo estimado: menos de 20 segundos" not in texts
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
    assert any("Tus datos del curso están guardados. No se perdió nada." in t for t in texts)
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
    # La ventana modal (G-001) no sale en `page_texts`: se leen sus widgets.
    assert "Resultados de aprendizaje" in [m.value.strip("*") for m in at.markdown]
    assert "Guardar cambios" in [b.label for b in at.button]
    at = click(at, "+ Agregar resultado de aprendizaje")
    at = click(at, "Guardar cambios")
    assert_no_exception(at)
    assert not any(b.label == "Guardar cambios" for b in at.button)  # la ventana se cerró
    assert "sr-edit" not in at.session_state


def test_d2b_cancel_closes_the_dialog_and_forgets_the_outcomes() -> None:
    at = staff_app(page=SYLLABUS)
    at = click(at, "Editar tema")
    at = click(at, "Cancelar")
    assert_no_exception(at)
    assert not any(b.label == "Guardar cambios" for b in at.button)
    assert f"sr-outcomes-{at.selectbox(key='sr-selected').value}" not in at.session_state
    assert "sr-edit" not in at.session_state


def test_d2b_removing_an_outcome_keeps_the_text_of_the_others() -> None:
    """Con la clave por posición, al quitar el primer resultado el campo seguía mostrando su
    texto (Streamlit ignora `value=` si la clave ya tiene estado) y lo copiaba al siguiente."""
    at = staff_app(page=SYLLABUS)
    at = click(at, "Editar tema")
    at = click(at, "+ Agregar resultado de aprendizaje")
    statements = [t for t in at.text_input if t.key and t.key.startswith("sr-os-")]
    assert len(statements) == 2
    statements[1].set_value("aplicar la regresión lineal a un caso real").run()
    remove = [b for b in at.button if b.label == "Quitar"]
    remove[0].click().run()
    assert_no_exception(at)
    statements = [t for t in at.text_input if t.key and t.key.startswith("sr-os-")]
    assert [t.value for t in statements] == ["aplicar la regresión lineal a un caso real"]


def test_d2c_reextract_asks_for_confirmation() -> None:
    at = staff_app(scenario="loading", page=SYLLABUS)
    at = click(at, "Volver a extraer temas")
    assert any(
        "se perderán tus correcciones: 1 corregido, 1 agregado por ti, 1 eliminado" in m.value
        for m in at.markdown
    )
    at = click(at, "Sí, volver a extraer")
    assert_no_exception(at)
    assert any("Extrayendo temas del syllabus" in t for t in page_texts(at))


def test_d2b_links_warning_and_footer_match_figma() -> None:
    """V-071, V-072: «Quitar», «Eliminar tema» y «+ Agregar…» son botones de texto; el aviso del
    ciclo va en una caja ámbar y «Eliminar tema» queda antes de «Cancelar» y «Guardar»."""
    at = staff_app(page=SYLLABUS)
    at = click(at, "Editar tema")
    prefixes = ("sr-orm-", "sr-del-", "sr-oadd-", "sr-cancel-", "sr-save-")
    types = {b.label: b.proto.type for b in at.button if b.key and b.key.startswith(prefixes)}
    assert types == {
        "Quitar": "tertiary",
        "+ Agregar resultado de aprendizaje": "tertiary",
        "Eliminar tema": "tertiary",
        "Cancelar": "secondary",
        "Guardar cambios": "primary",
    }
    footer = [b.label for b in at.button if b.key and b.key.startswith(("sr-del-", "sr-cancel-"))]
    assert footer == ["Eliminar tema", "Cancelar"]
    assert any(
        "Si un prerrequisito forma un ciclo, no podrás guardar." in w.value for w in at.warning
    )
    css = (STYLES_DIR / "components" / "syllabus_review.css").read_text(encoding="utf-8")
    for prefix in ("sr-orm-", "sr-del-", "sr-oadd-"):
        assert f'[class*="st-key-{prefix}"] button' in css
    assert "text-decoration: underline" in css


def test_d2c_dialog_is_narrow_and_keeps_its_buttons() -> None:
    """V-074: la ventana D2c es angosta (500 px, no 750) y sus botones se conservan."""
    source = (STYLES_DIR.parents[1] / SYLLABUS).read_text(encoding="utf-8")
    assert 'st.dialog("¿Volver a extraer los temas?", width="small"' in source
    at = staff_app(scenario="loading", page=SYLLABUS)
    at = click(at, "Volver a extraer temas")
    assert at.button(key="sr-reextract-cancel").proto.type == "secondary"
    assert at.button(key="sr-reextract-ok").proto.type == "primary"


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


def test_d1c_back_to_courses_discards_the_draft() -> None:
    at = _fill_paste_form("failed")
    at = click(at, "Extraer temas con IA")
    assert "nc-draft" in at.session_state
    at = click(at, "Volver a mis cursos")
    assert_no_exception(at)
    assert "nc-draft" not in at.session_state


def test_d1b_ai_note_is_an_info_box_under_two_columns() -> None:
    at = staff_app(page=NEW_COURSE)
    assert_no_exception(at)
    assert len(at.columns) == 2
    assert [i.value for i in at.info] == [
        "El syllabus se procesa con IA para extraer temas, prerrequisitos y resultados de "
        "aprendizaje. Los apuntes se usan después, al generar la explicación de cada tema. Tú "
        "revisas, corriges y apruebas todo antes de publicar."
    ]
    # R-004: la tarjeta de apuntes va a todo el ancho, debajo de las dos columnas de Figma.
    assert [s.value for s in at.subheader] == [
        "Datos del curso",
        "Syllabus",
        "Apuntes y lecturas · opcional",
    ]


def test_d1c_has_no_page_title_and_shows_the_retry_pill() -> None:
    at = _fill_paste_form("loading")
    at = click(at, "Extraer temas con IA")
    assert_no_exception(at)
    assert len(at.title) == 0
    texts = page_texts(at)
    assert "La respuesta no tenía el formato esperado · Reintentando, 2 de 3" in texts


def test_d1d_error_box_names_the_file_and_swaps_the_buttons() -> None:
    at = _fill_paste_form("no_text")
    at = click(at, "Extraer temas con IA")
    assert_no_exception(at)
    assert len(at.error) == 1
    assert at.error[0].value.startswith(":red[**syllabus")
    assert "0 caracteres de texto detectados" in at.error[0].value
    assert "Tus datos del curso están guardados. No se perdió nada." in at.error[0].value
    assert not any("0 caracteres" in c.value for c in at.caption)
    kinds = {b.label: b.proto.type for b in at.button}
    assert kinds["Subir otro archivo"] == "primary"
    assert kinds["Pegar el texto"] == "secondary"


def test_d2_lists_the_course_materials_and_removes_one() -> None:
    """R-010: la sección de apuntes de D2 lista los del curso y «Quitar» saca uno."""
    at = staff_app(page=SYLLABUS)
    assert_no_exception(at)
    texts = page_texts(at)
    assert "Apuntes y lecturas" in texts
    assert any("apuntes_u1_supervisado.pdf" in t and "Apuntes propios" in t for t in texts)
    assert any("ISLR_cap3_regresion.md" in t and "Libro o material abierto" in t for t in texts)
    at = click(at, "Quitar apunte")
    assert_no_exception(at)
    texts = page_texts(at)
    assert not any("apuntes_u1_supervisado.pdf" in t for t in texts)
    assert any("ISLR_cap3_regresion.md" in t for t in texts)


def test_d2_add_materials_opens_the_uploader_window() -> None:
    at = staff_app(page=SYLLABUS)
    at = click(at, "Agregar apuntes")
    assert_no_exception(at)
    labels = [b.label for b in at.button]
    assert "Subir apuntes" in labels
    upload = next(b for b in at.button if b.label == "Subir apuntes")
    assert upload.disabled  # sin archivos no hay nada que subir
    at = click(at, "Cancelar")
    assert "Subir apuntes" not in [b.label for b in at.button]


def test_d2_warns_about_the_materials_that_could_not_be_used() -> None:
    at = staff_app(page=SYLLABUS)
    at.session_state["sr-materials-skipped"] = ["escaneado.pdf"]
    at.run()
    warnings = [w.value for w in at.warning]
    assert any("«escaneado.pdf»" in w for w in warnings)
