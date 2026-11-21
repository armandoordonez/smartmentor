"""Pulido visual de staff (V-097 a V-101) y B-057: D1c, D2, D2b, AD2, D5c, D1b y la barra."""

from typing import Any

import httpx
import pytest
import respx
from apptest import container_keys, page_texts
from staff_support import (
    assert_no_exception,
    click,
    staff_app,
    staff_text_reader,  # noqa: F401
)
from streamlit.proto.LabelVisibility_pb2 import LabelVisibility
from streamlit.testing.v1 import AppTest

from clients.api import ApiClient
from clients.fixtures import FixturesClient
from clients.models import Page
from clients.models_staff import Course, CourseTopic, SyllabusInfo, TopicWrite
from core.polling import WAIT_MODE_KEY
from core.styles import STYLES_DIR

NEW_COURSE = "pages/instructor/new_course.py"
SYLLABUS = "pages/instructor/syllabus_review.py"
LLM_LOGS = "pages/admin/llm_logs.py"
USERS = "pages/admin/users.py"
VISIBLE = LabelVisibility.LabelVisibilityOptions.VISIBLE
COLLAPSED = LabelVisibility.LabelVisibilityOptions.COLLAPSED


def _css(name: str) -> str:
    return (STYLES_DIR / name).read_text(encoding="utf-8")


def _edit_topic(topic_id: int) -> AppTest:
    at = staff_app(page=SYLLABUS)
    at.selectbox(key="sr-selected").set_value(topic_id).run()
    return click(at, "Editar tema")


# --- D2b · Editar tema ---------------------------------------------------------------------------


def test_d2b_subtopics_go_in_one_line_separated_by_dots() -> None:
    """Figma pone los subtemas en una sola línea separada por «·», no en varias líneas."""
    at = _edit_topic(103)
    assert not any(t.key == "sr-sub-103" for t in at.text_area)
    field = at.text_input(key="sr-sub-103")
    assert field.value == "Función sigmoide · Umbral de decisión · Métricas de clasificación"


def test_d2b_saving_splits_the_subtopics_on_the_dot(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[TopicWrite] = []

    def update_topic(self: FixturesClient, topic_id: int, body: TopicWrite) -> CourseTopic:
        del topic_id
        sent.append(body)
        return self.create_topic(1, body)

    monkeypatch.setattr(FixturesClient, "update_topic", update_topic)
    at = _edit_topic(103)
    at.text_input(key="sr-sub-103").set_value("Sigmoide ·  Umbral · · Métricas").run()
    at = click(at, "Guardar cambios")
    assert_no_exception(at)
    assert [body.subtopics for body in sent] == [["Sigmoide", "Umbral", "Métricas"]]


def test_d2b_bloom_label_shows_once_and_the_prerequisites_placeholder_is_in_spanish() -> None:
    """«Verbo de Bloom» se ve sobre el primer resultado y las demás filas la conservan oculta
    (nombre accesible); el selector de prerrequisitos no dice «Choose options» (B-057)."""
    at = _edit_topic(103)
    at = click(at, "+ Agregar resultado de aprendizaje")
    verbs = [s for s in at.selectbox if s.key and s.key.startswith("sr-ob-103-")]
    assert len(verbs) >= 2
    assert {s.label for s in verbs} == {"Verbo de Bloom"}
    assert [s.proto.label_visibility.value for s in verbs] == [VISIBLE] + [COLLAPSED] * (
        len(verbs) - 1
    )
    assert at.multiselect(key="sr-pre-103").proto.placeholder == "Elige los temas previos"


def test_other_multiselects_and_empty_selectboxes_have_spanish_placeholders() -> None:
    """B-057: el mismo texto en inglés de los demás selectores con valor vacío."""
    at = staff_app(role="admin", page=USERS)
    at = click(at, "Crear usuario")
    assert at.multiselect(key="u-new-roles").proto.placeholder == "Elige los roles"


# --- D2 · enlaces y subtítulo --------------------------------------------------------------------


def test_d2_links_are_blue_and_underlined_like_the_figma_ones() -> None:
    """«Volver a extraer temas» (abajo) y «Ver los temas como grafo» son enlaces azules."""
    at = staff_app(page=SYLLABUS)
    keyed = {b.key: b.proto.type for b in at.button if b.key}
    assert keyed["sr-reextract-bottom"] == "tertiary"
    assert keyed["sr-graph"] == "tertiary"
    css = _css("components/syllabus_review.css")
    for key in ("sr-reextract-bottom", "sr-graph"):
        assert f".st-key-{key} button" in css
    block = css.split("V-097")[1]
    assert "color: var(--learner-text)" in block
    assert "text-decoration: underline" in block


def _course_with_syllabus(monkeypatch: pytest.MonkeyPatch, syllabus: SyllabusInfo | None) -> None:
    """Los datos de ejemplo traen el archivo del syllabus; la API real todavía no lo manda."""
    original_get, original_list = FixturesClient.get_course, FixturesClient.list_courses

    def get_course(self: FixturesClient, course_id: int) -> Course:
        course = original_get(self, course_id)
        course.syllabus = syllabus
        return course

    def list_courses(self: FixturesClient, **kwargs: Any) -> Page[Course]:
        page = original_list(self, **kwargs)
        for course in page.items:
            course.syllabus = syllabus
        return page

    monkeypatch.setattr(FixturesClient, "get_course", get_course)
    monkeypatch.setattr(FixturesClient, "list_courses", list_courses)


def _subtitle(at: AppTest) -> str:
    return next(c.value for c in at.caption if c.value.startswith("EN REVISIÓN"))


def test_d2_subtitle_shows_the_file_and_pages_when_the_course_has_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Figma dice «EN REVISIÓN · archivo.pdf · N páginas»."""
    assert (
        _subtitle(staff_app(page=SYLLABUS)) == "EN REVISIÓN · syllabus_ML_2026-2.pdf · 12 páginas"
    )
    _course_with_syllabus(monkeypatch, SyllabusInfo(filename="programa.pdf", pages=3))
    assert _subtitle(staff_app(page=SYLLABUS)) == "EN REVISIÓN · programa.pdf · 3 páginas"


def test_d2_subtitle_keeps_only_what_the_api_sends(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin datos del archivo no se inventa nada: queda solo el estado."""
    _course_with_syllabus(monkeypatch, None)
    assert _subtitle(staff_app(page=SYLLABUS)) == "EN REVISIÓN"
    _course_with_syllabus(monkeypatch, SyllabusInfo(filename="solo-nombre.pdf"))
    assert _subtitle(staff_app(page=SYLLABUS)) == "EN REVISIÓN · solo-nombre.pdf"
    _course_with_syllabus(monkeypatch, SyllabusInfo(pages=8))
    assert _subtitle(staff_app(page=SYLLABUS)) == "EN REVISIÓN · 8 páginas"


@respx.mock
def test_d2_subtitle_shows_file_and_pages_from_the_api_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B-065: el curso llega por HTTP con `syllabus` y D2 arma el subtítulo con él."""
    base = "http://api.test"
    body = {
        "id": 1,
        "name": "Machine Learning",
        "status": "in_review",
        "owner_user_id": 3,
        "topics_count": 4,
        "enrolled_count": 0,
        "syllabus": {"filename": "plan-api.pdf", "pages": 9, "characters": 5000},
    }
    respx.get(f"{base}/api/v1/courses/1").mock(return_value=httpx.Response(200, json=body))
    api_course = ApiClient(
        base, lambda: "test-only-not-a-secret", http=httpx.Client(base_url=base)
    ).get_course(1)
    _course_with_syllabus(monkeypatch, api_course.syllabus)
    assert _subtitle(staff_app(page=SYLLABUS)) == "EN REVISIÓN · plan-api.pdf · 9 páginas"


# --- D1c · espera sin «Cargando…» ----------------------------------------------------------------


def _extracting(scenario: str) -> AppTest:
    at = staff_app(scenario=scenario, page=NEW_COURSE)
    at.get("button_group")[0].set_value("Pegar texto").run()
    at.text_input(key="nc-name").set_value("Curso de prueba")
    at.run()
    at.text_area(key="nc-text").set_value("Tema 1: introducción").run()
    return click(at, "Extraer temas con IA")


def test_d1c_estimate_does_not_promise_a_short_time() -> None:
    texts = page_texts(_extracting("loading"))
    assert "Tiempo estimado: hasta 2 minutos" in texts
    assert not any("20 segundos" in t for t in texts)


def test_d1c_polling_runs_in_wait_mode_so_the_spinner_stays_quiet() -> None:
    """Durante la extracción el sondeo no dibuja «Cargando…» sobre la tarjeta de carga; si el
    trabajo falla, el modo espera se apaga para que «Reintentar» y «Volver» sí lo muestren."""
    at = _extracting("loading")
    assert at.session_state[WAIT_MODE_KEY][1] == at.session_state["staff_state"].job_id
    assert WAIT_MODE_KEY not in _extracting("failed").session_state


# --- AD2 y D5c: estilos ---------------------------------------------------------------------------


def test_kpi_cards_put_the_value_above_the_label() -> None:
    """AD2 y D3: el número grande arriba y la etiqueta abajo, invirtiendo el orden solo en CSS."""
    at = staff_app(role="admin", page=LLM_LOGS)
    assert_no_exception(at)
    assert {"Llamadas", "Costo total", "Latencia p95", "JSON inválido"} <= {
        m.label for m in at.metric
    }
    css = _css("components/kpi_cards.css")
    assert "flex-direction: column-reverse" in css


def test_d5c_criteria_pills_and_llm_note_follow_figma() -> None:
    css = _css("components/grading.css")
    assert 'button[role="radio"]:nth-of-type(1)[aria-checked="true"]' in css
    assert "var(--instructor-soft)" in css and "var(--error-soft)" in css
    assert ".st-key-grading-llm-note h3" in css


# --- D1b y barra superior ---------------------------------------------------------------------


def test_d1b_dropzones_and_avatar_have_their_figma_styles() -> None:
    new_course = _css("components/new_course.css")
    assert ".st-key-nc-file section" in new_course
    assert "dashed var(--learner-accent)" in new_course
    assert "dashed var(--learner-accent)" in _css("components/material_uploader.css")
    assert "border-radius: 50%" in _css("layout.css")


def test_header_wraps_the_account_menu_in_the_avatar_container() -> None:

    at = staff_app(page=NEW_COURSE)
    assert "app-avatar" in container_keys(at)
