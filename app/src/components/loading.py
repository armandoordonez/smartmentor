"""Indicador «Cargando…» para las peticiones normales a la API.

Es un único `st.spinner`: Streamlit lo dibuja solo si la petición tarda más de 0,5 s
(`DELAY_SECS`), así que las respuestas rápidas no parpadean. No reemplaza las pantallas de espera
de la IA (U1a a U1d, `loading_steps.py`).
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

LOADING_TEXT = "Cargando…"

# Peticiones en curso en esta ejecución del guion; el script de Streamlit corre en un solo hilo.
_depth: ContextVar[int] = ContextVar("loading_depth", default=0)


def _never_quiet() -> bool:
    return False


# «Modo espera» (T-054): dentro de una pantalla de espera de la IA (U1x) ya hay una tarjeta de
# carga, así que `core/polling.py` registra aquí cómo saberlo y el spinner no se dibuja encima.
# El componente no lee la sesión: solo pregunta a la función registrada.
_quiet_probe: Callable[[], bool] = _never_quiet


def set_quiet_probe(probe: Callable[[], bool]) -> None:
    """Registra la función que dice si el spinner debe callarse (modo espera)."""
    global _quiet_probe
    _quiet_probe = probe


@contextmanager
def loading_indicator() -> Iterator[None]:
    """Muestra «Cargando…» mientras dura el bloque.

    No se anida: si ya hay un indicador activo, el bloque interno no dibuja otro. Sin contexto de
    Streamlit (pruebas del cliente con `respx`, scripts) no hace nada, y en modo espera (U1x)
    tampoco: la tarjeta de carga ya está en pantalla.
    """
    if _depth.get() > 0 or get_script_run_ctx(suppress_warning=True) is None or _quiet_probe():
        yield
        return
    token = _depth.set(1)
    try:
        with st.spinner(LOADING_TEXT):
            yield
    finally:
        _depth.reset(token)
