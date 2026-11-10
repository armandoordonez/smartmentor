"""D3, D3b (ruta y avance, configurar) y D4 a D4c (detalle del aprendiz, intentos extra)."""

from apptest import page_texts
from staff_support import (
    assert_matches_figma,
    assert_no_exception,
    click,
    staff_app,
    with_state,
)

DASHBOARD = "pages/instructor/path_dashboard.py"
DETAIL = "pages/instructor/learner_detail.py"

KPI_TEXTS = ("18", "Inscritos", "44 %", "Finalización", "6", "Badges emitidos", "1,6")


def test_d3_matches_figma() -> None:
    at = staff_app(page=DASHBOARD)
    assert_matches_figma(
        at,
        "D3",
        # `st.metric` pone la etiqueta arriba y el valor abajo, y AppTest no lee las métricas
        # (se prueban aparte); los valores de un solo carácter coincidirían con cualquier texto.
        ignore=(*KPI_TEXTS, "Intentos por tema"),
        accepted=(
            # «Guardar cambios» es del panel de D3b (se abre con «Configurar ruta»).
            "Guardar cambios",
            # Los nombres de tema abreviados de Figma salen completos de la API.
            "2 · REG. LINEAL",
            "3 · REG. LOGÍSTICA",
        ),
    )


def test_d3_kpis_are_streamlit_metrics() -> None:
    at = staff_app(page=DASHBOARD)
    values = {m.label: m.value for m in at.metric}
    assert values["Inscritos"] == "18"
    assert values["Finalización"] == "44 %"
    assert values["Intentos por tema"] == "1,6"


def test_d3_empty_group() -> None:
    at = staff_app(scenario="empty")
    with_state(at, path_id=11).switch_page(DASHBOARD).run()
    assert_no_exception(at)
    assert any("Todavía no hay aprendices" in t for t in page_texts(at))
    at = staff_app(scenario="empty", page=DASHBOARD)
    assert any("Todavía no tienes rutas" in t for t in page_texts(at))


def test_d3_forbidden_and_error() -> None:
    at = staff_app(scenario="forbidden", page=DASHBOARD)
    assert "403" in page_texts(at, skip_header=False)
    at = staff_app(scenario="error", page=DASHBOARD)
    assert_no_exception(at)
    assert at.error


def test_d3b_configure_saves_thresholds() -> None:
    at = staff_app(page=DASHBOARD)
    at = click(at, "Configurar ruta")
    texts = page_texts(at)
    assert "Configurar la ruta" in texts and "UMBRALES" in texts
    assert "Aprobar un tema" in [n.label for n in at.number_input]
    assert not any("Durante el piloto" in t for t in texts)
    at.number_input(key="pd-topic").set_value(75).run()
    at = click(at, "Guardar")
    assert_no_exception(at)
    assert "Configurar la ruta" not in page_texts(at)


def test_d3b_pilot_running_asks_for_confirmation() -> None:
    at = staff_app(scenario="pilot_running", page=DASHBOARD)
    at = click(at, "Configurar ruta")
    texts = page_texts(at)
    assert any("Durante el piloto, cambiar los umbrales" in t for t in texts)
    assert next(b for b in at.button if b.label == "Guardar").disabled
    at.checkbox(key="pd-ok").check().run()
    at = click(at, "Guardar")
    assert_no_exception(at)
    assert "Configurar la ruta" not in page_texts(at)


def test_d3_clicking_a_learner_opens_the_detail() -> None:
    at = staff_app(page=DASHBOARD)
    at = click(at, "Ver detalle")
    assert_no_exception(at)
    assert any(t == "PERFIL Y OBJETIVO" for t in page_texts(at))


def _detail(enrollment_id: int, scenario: str = "default"):  # type: ignore[no-untyped-def]
    at = staff_app(scenario=scenario, page=DASHBOARD)
    with_state(at, path_id=11, enrollment_id=enrollment_id).switch_page(DETAIL).run()
    return at


def test_d4_matches_figma() -> None:
    at = _detail(201)
    assert_matches_figma(at, "D4")


def test_d4b_exhausted_attempts_matches_figma() -> None:
    at = _detail(204)
    assert_matches_figma(at, "D4b", accepted=())


def test_d4c_grant_attempts() -> None:
    at = _detail(204)
    at = click(at, "Habilitar nuevos intentos")
    texts = page_texts(at)
    assert "Intentos que se habilitan" in [s.label for s in at.selectbox]
    assert any("Cada intento trae preguntas nuevas" in t for t in texts)
    at = click(at, "Habilitar intentos")
    assert_no_exception(at)
    assert not any(s.label == "Intentos que se habilitan" for s in at.selectbox)


def test_d4_without_selection_asks_to_choose() -> None:
    at = staff_app(page=DETAIL)
    assert_no_exception(at)
    assert any("Elige un aprendiz" in t for t in page_texts(at))
