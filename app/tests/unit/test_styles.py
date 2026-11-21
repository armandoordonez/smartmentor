"""Estilos: un solo lugar para los colores (ADR 0017, plan 5.5.1 y 18.2).

- Sin hexadecimales ni `rgb()` fuera de `tokens.css` (ni en el CSS ni en el código Python).
- Toda `var(--x)` usada está definida.
- `.streamlit/config.toml` coincide con `tokens.css`.
- El contraste de los pares de colores cumple WCAG: 4,5:1 texto y 3:1 bordes de campos.
- El CSS no tiene `<` seguido de una letra, ni siquiera en comentarios: DOMPurify (el saneador de
  `st.html`) descarta el `<style>` entero y la app queda sin estilos (B-014).
"""

import re
import tomllib
from pathlib import Path

import pytest
from support import APP_DIR, SRC_DIR

from core.styles import STYLES_DIR, build_css, style_files, token

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
COLOR_FUNCTION = re.compile(r"\b(?:rgb|rgba|hsl|hsla)\(", re.IGNORECASE)
VAR_USE = re.compile(r"var\(\s*--([a-z0-9-]+)")
VAR_DEF = re.compile(r"(?<![a-z0-9-])--([a-z0-9-]+)\s*:")
COMMENTS = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_FILES = sorted(STYLES_DIR.rglob("*.css"))
NON_TOKEN_CSS = [path for path in CSS_FILES if path.name != "tokens.css"]
# Variables que fijan los contenedores de rol y se usan con respaldo en base.css y componentes.
ROLE_VARIABLES = {"accent", "accent-soft", "accent-text"}


def _code(path: Path) -> str:
    return COMMENTS.sub("", path.read_text(encoding="utf-8"))


def test_style_files_are_loaded_in_fixed_order() -> None:
    names = [path.relative_to(STYLES_DIR).as_posix() for path in style_files()]
    assert names[:4] == ["tokens.css", "base.css", "layout.css", "roles.css"]
    assert names[4:] == sorted(names[4:])
    assert all(name.startswith("components/") for name in names[4:])
    assert {path.relative_to(STYLES_DIR).as_posix() for path in CSS_FILES} == set(names)


def test_build_css_includes_every_file() -> None:
    css = build_css()
    for path in CSS_FILES:
        assert f"/* {path.relative_to(STYLES_DIR).as_posix()} */" in css


def test_the_css_has_nothing_that_looks_like_an_html_tag() -> None:
    """B-014: con `.st-key-<nombre>` en un comentario, DOMPurify descartaba todos los estilos."""
    found = re.findall(r"<[/!a-zA-Z][^>]{0,30}", build_css())
    assert not found, f"usa {{nombre}} en lugar de <nombre> en el CSS: {found}"


@pytest.mark.parametrize("path", NON_TOKEN_CSS, ids=lambda p: p.name)
def test_no_hex_or_color_functions_outside_tokens(path: Path) -> None:
    code = _code(path)
    assert not HEX.findall(code), f"{path.name} tiene hexadecimales; usa var(--token)"
    assert not COLOR_FUNCTION.findall(code), f"{path.name} usa rgb()/hsl(); usa var(--token)"


def test_no_hex_in_python_sources() -> None:
    """Ni páginas ni componentes escriben colores: salen de `tokens.css` (`core.styles.token`)."""
    offenders = []
    for path in SRC_DIR.rglob("*.py"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if HEX.search(line) or COLOR_FUNCTION.search(line):
                offenders.append(f"{path.relative_to(SRC_DIR)}:{number}")
    assert offenders == []


def test_every_used_variable_is_defined() -> None:
    defined = set(VAR_DEF.findall(_code(STYLES_DIR / "tokens.css")))
    for path in CSS_FILES:
        defined |= set(VAR_DEF.findall(_code(path)))
    used = set()
    for path in CSS_FILES:
        used |= set(VAR_USE.findall(_code(path)))
    assert used - defined == set()
    assert defined >= ROLE_VARIABLES


def test_tokens_define_the_figma_variables() -> None:
    figma = {
        "text-primary", "text-secondary", "text-tertiary", "text-on-accent",
        "bg-page", "bg-surface", "bg-subtle", "bg-neutral",
        "border-default", "border-strong",
        "learner-accent", "learner-soft", "learner-text",
        "instructor-accent", "instructor-soft", "instructor-text",
        "admin-accent", "admin-soft", "admin-text",
        "warning-accent", "warning-soft", "warning-text",
        "error-accent", "error-soft", "error-text",
    }  # fmt: skip
    # Las 24 variables de Figma más `error-accent`, cuyo nombre es inferido (sin valor en Figma).
    for name in figma:
        assert re.fullmatch(r"#[0-9a-f]{6}", token(name)), name


def test_warning_accent_is_never_used_as_text_color() -> None:
    """`aviso/acento` da 2,77:1 sobre blanco: solo puede ser decorativo."""
    for path in CSS_FILES:
        for line in _code(path).splitlines():
            if "warning-accent" in line:
                assert not re.match(r"\s*(?:color|-webkit-text-fill-color)\s*:", line), path.name


# --- .streamlit/config.toml coincide con tokens.css --------------------------------------------

CONFIG = tomllib.loads((APP_DIR / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
THEME_TO_TOKEN = {
    "primaryColor": "learner-accent",
    "backgroundColor": "bg-page",
    "secondaryBackgroundColor": "bg-surface",
    "textColor": "text-primary",
    "borderColor": "border-field",
    "linkColor": "learner-text",
    "greenColor": "instructor-accent",
    "greenBackgroundColor": "instructor-soft",
    "greenTextColor": "instructor-text",
    "blueColor": "learner-accent",
    "blueBackgroundColor": "learner-soft",
    "blueTextColor": "learner-text",
    "orangeColor": "warning-text",
    "orangeBackgroundColor": "warning-soft",
    "orangeTextColor": "warning-text",
    "yellowColor": "warning-text",
    "yellowBackgroundColor": "warning-soft",
    "yellowTextColor": "warning-text",
    "grayColor": "text-secondary",
    "grayBackgroundColor": "bg-neutral",
    "grayTextColor": "text-secondary",
    "violetColor": "admin-accent",
    "violetBackgroundColor": "admin-soft",
    "violetTextColor": "admin-text",
    "redColor": "error-text",
    "redBackgroundColor": "error-soft",
    "redTextColor": "error-text",
}


@pytest.mark.parametrize(("key", "name"), THEME_TO_TOKEN.items())
def test_config_theme_matches_tokens(key: str, name: str) -> None:
    assert CONFIG["theme"][key].lower() == token(name).lower()


def test_config_chart_palette_comes_from_tokens() -> None:
    expected = ["learner-accent", "instructor-accent", "admin-accent", "warning-text"]
    palette = [color.lower() for color in CONFIG["theme"]["chartCategoricalColors"]]
    assert palette[:4] == [token(name).lower() for name in expected]
    assert palette[4].lower() == token("text-secondary").lower()


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def test_every_hex_in_config_is_a_token() -> None:
    token_values = {token(name).lower() for name in _all_token_names()}
    colors = [text for text in _strings(CONFIG) if HEX.fullmatch(text)]
    assert colors
    for color in colors:
        assert color.lower() in token_values, color


def _all_token_names() -> list[str]:
    css = _code(STYLES_DIR / "tokens.css")
    return [name for name in VAR_DEF.findall(css) if re.fullmatch(r"#[0-9a-f]{6}", token(name))]


# --- Contraste (WCAG 2.2) ------------------------------------------------------------------------


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted((_luminance(token(foreground)), _luminance(token(background))))[::-1]
    return (lighter + 0.05) / (darker + 0.05)


TEXTS = ("text-primary", "text-secondary", "text-tertiary")
BACKGROUNDS = ("bg-page", "bg-surface", "bg-subtle", "bg-neutral")
TEXT_PAIRS = (
    [(text, bg) for text in TEXTS for bg in BACKGROUNDS]
    + [(f"{role}-text", f"{role}-soft") for role in ("learner", "instructor", "admin")]
    + [(f"{role}-text", "bg-surface") for role in ("learner", "instructor", "admin")]
    + [(f"{role}-accent", "bg-surface") for role in ("learner", "instructor", "admin")]
    + [("text-on-accent", f"{role}-accent") for role in ("learner", "instructor", "admin")]
    + [("warning-text", "warning-soft"), ("warning-text", "bg-surface")]
    + [("error-text", "error-soft"), ("error-text", "bg-surface")]
    + [("error-accent", "bg-surface")]
)


@pytest.mark.parametrize(("foreground", "background"), TEXT_PAIRS)
def test_text_contrast_is_at_least_4_5(foreground: str, background: str) -> None:
    assert contrast(foreground, background) >= 4.5, (
        foreground,
        background,
        round(contrast(foreground, background), 2),
    )


@pytest.mark.parametrize("background", ["bg-surface", "bg-page"])
def test_field_border_contrast_is_at_least_3(background: str) -> None:
    assert contrast("border-field", background) >= 3.0


def test_figma_borders_do_not_reach_3_but_are_decorative() -> None:
    """`borde/default` y `borde/fuerte` no sirven como borde de campo: de ahí `--border-field`."""
    assert contrast("border-default", "bg-surface") < 3.0
    assert contrast("border-strong", "bg-surface") < 3.0


def test_warning_accent_fails_text_contrast_on_white() -> None:
    assert round(contrast("warning-accent", "bg-surface"), 2) == pytest.approx(2.77, abs=0.01)
