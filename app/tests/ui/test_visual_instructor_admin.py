"""Correcciones visuales frente a Figma v3: A1, D3b, D4b, D4c y C4 (V-058 a V-087)."""

import re

from apptest import new_app, page_texts
from staff_support import (
    assert_no_exception,
    click,
    staff_app,
    staff_text_reader,  # noqa: F401  (fixture autouse)
    with_state,
)
from support import APP_DIR

from services.staff_prompts import PROMPTS

DASHBOARD = "pages/instructor/path_dashboard.py"
DETAIL = "pages/instructor/learner_detail.py"
CATALOG = "pages/admin/prompt_catalog.py"
STYLES = APP_DIR / "src" / "static" / "styles" / "components"


def _css(name: str) -> str:
    return (STYLES / name).read_text("utf-8")


# --- A1 ----------------------------------------------------------------------------------------


def test_a1_role_card_css_colors_border_and_button_per_role() -> None:
    css = _css("role_card.css")
    assert "border-width: 2px" in css
    for role, token in (("learner", "learner"), ("instructor", "instructor"), ("admin", "admin")):
        assert f".st-key-card-role-{role} {{" in css
        assert f"--role-accent: var(--{token}-accent)" in css
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b", css)


def test_a1_buttons_are_secondary_so_the_card_color_applies() -> None:
    at = new_app().run()
    assert_no_exception(at)
    for role in ("learner", "instructor", "admin"):
        assert at.button(key=f"enter-{role}").proto.type == "secondary"


def test_a1_permissions_go_in_two_separate_lines() -> None:
    at = new_app().run()
    permissions = [m.value for m in at.markdown if m.value.startswith("Puede:")]
    assert len(permissions) == 3
    for value in permissions:
        can, cannot_or_note = value.split("  \n")
        assert can.startswith("Puede:") and cannot_or_note


# --- D3b ---------------------------------------------------------------------------------------


def test_d3b_thresholds_show_label_and_description_beside_a_short_field() -> None:
    at = staff_app(page=DASHBOARD)
    at = click(at, "Configurar ruta")
    assert_no_exception(at)
    captions = [c.value for c in at.caption]
    assert "Puntaje mínimo en la evaluación final." in captions
    assert "Cada intento trae preguntas nuevas." in captions
    assert "**Obtener el badge**" in [m.value for m in at.markdown]
    # Las etiquetas siguen en el widget (accesibilidad) aunque no se vean.
    assert {n.label for n in at.number_input} >= {"Aprobar un tema", "Intentos por evaluación"}
    assert at.number_input(key="pd-topic").value == 70


def test_d3b_eyebrows_are_blue() -> None:
    at = staff_app(page=DASHBOARD)
    at = click(at, "Configurar ruta")
    markdown = [m.value for m in at.markdown]
    assert ":small[:blue[**UMBRALES**]]" in markdown
    assert ":small[:blue[**OBJETIVO POR DEFECTO · OPCIONAL**]]" in markdown


# --- D4b y D4c ---------------------------------------------------------------------------------


def _detail(enrollment_id: int = 204):  # type: ignore[no-untyped-def]
    at = staff_app(page=DASHBOARD)
    with_state(at, path_id=11, enrollment_id=enrollment_id).switch_page(DETAIL).run()
    return at


def test_d4b_exhausted_card_has_amber_title_and_a_primary_button() -> None:
    at = _detail()
    assert_no_exception(at)
    title = next(m.value for m in at.markdown if "intentos usados" in m.value)
    assert title.startswith(":orange[**Regresión lineal**")
    assert at.button(key="ld-grant").proto.type == "primary"
    css = _css("learner_detail.css")
    assert ".st-key-panel-exhausted" in css and "var(--warning-soft)" in css


def test_d4b_back_link_uses_the_role_color_and_level_bars_get_a_rail() -> None:
    css = _css("learner_detail.css")
    assert re.search(r"\.st-key-ld-back button[^{]*\{[^}]*var\(--accent\)", css)
    assert re.search(r"\.st-key-ld-level-bars [^{]*stProgressBarTrack[^{]*\{[^}]*--bg-neutral", css)
    assert "Volver a la ruta" in {b.label.replace("‹ ", "") for b in _detail().button}


def test_d4c_defaults_to_three_attempts_and_shows_the_note_in_an_info_box() -> None:
    at = _detail()
    at = click(at, "Habilitar nuevos intentos")
    assert at.selectbox(key="ld-n").value == 3
    assert any("Cada intento trae preguntas nuevas" in i.value for i in at.info)


# --- C4 ----------------------------------------------------------------------------------------


def test_c4_what_it_does_describes_every_prompt() -> None:
    assert all(len(p.description) > len(p.name) for p in PROMPTS)
    at = staff_app("admin", page=CATALOG)
    assert_no_exception(at)
    texts = page_texts(at)
    for prompt in PROMPTS:
        assert f"{prompt.name} · {prompt.description}" in texts
