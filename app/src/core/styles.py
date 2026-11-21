"""Cargador único de los estilos (ADR 0017, sección 5.5.1 del plan).

Lee `static/styles/` en un orden fijo (tokens, base, layout, roles y componentes) y lo inyecta con
`st.html` una vez por ejecución. Con `APP_ENV=local` se relee de disco en cada ejecución para ver
los cambios al guardar; en los demás entornos se guarda en caché.

El CSS es propio del proyecto: solo se inyecta desde archivos versionados, nunca texto del usuario
ni de la IA.
"""

import re
from functools import lru_cache
from pathlib import Path

import streamlit as st

from core.config import get_settings

STYLES_DIR = Path(__file__).resolve().parents[1] / "static" / "styles"
ORDERED_FILES = ("tokens.css", "base.css", "layout.css", "roles.css")


def style_files(directory: Path = STYLES_DIR) -> list[Path]:
    """Archivos CSS en el orden de carga: los fijos y luego `components/*.css` por nombre."""
    fixed = [directory / name for name in ORDERED_FILES]
    components = sorted((directory / "components").glob("*.css"))
    return [*fixed, *components]


def build_css(directory: Path = STYLES_DIR) -> str:
    """Concatena los archivos de estilos, cada uno precedido de un comentario con su nombre."""
    parts = []
    for path in style_files(directory):
        parts.append(f"/* {path.relative_to(directory)} */\n{path.read_text(encoding='utf-8')}")
    return "\n".join(parts)


@lru_cache(maxsize=1)
def _cached_css() -> str:
    return build_css()


def current_css() -> str:
    """CSS vigente: sin caché con `APP_ENV=local`, en caché en los demás entornos."""
    if get_settings().app_env == "local":
        return build_css()
    return _cached_css()


def inject_styles() -> None:
    """Inyecta el CSS de la aplicación en la página actual."""
    st.html(f"<style>{current_css()}</style>")


_TOKEN = re.compile(r"--(?P<name>[a-z0-9-]+)\s*:\s*(?P<value>[^;]+);")


@lru_cache(maxsize=1)
def _tokens() -> dict[str, str]:
    css = (STYLES_DIR / "tokens.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    return {m["name"]: m["value"].strip() for m in _TOKEN.finditer(css)}


def token(name: str) -> str:
    """Valor de un token de `tokens.css` (por ejemplo `learner-accent`), sin los dos guiones.

    Es para lo que no acepta variables CSS (como el DOT de Graphviz): así los colores siguen
    saliendo de un solo archivo.
    """
    return _tokens()[name]
