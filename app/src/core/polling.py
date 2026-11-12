"""Sondeo de trabajos desde un `st.fragment`, con el vencimiento del token resuelto.

Los fragmentos se ejecutan fuera del `try/except` de `main.py`: un 401 dentro de ellos mostraba el
traceback de Streamlit en vez de A7 «Tu sesión expiró». Aquí un error global (401, 403 de rol) pide
una ejecución completa de la aplicación, que sí pasa por `main.py` y dibuja la pantalla de estado.
"""

from collections.abc import Callable

import streamlit as st

from clients.base import ApiError
from clients.models import Job
from core.errors import is_global
from core.staff_errors import show_staff_error


def poll_job_or_rerun(fetch: Callable[[], Job]) -> Job | None:
    """Devuelve el trabajo, o `None` si hubo un error ya mostrado (la página sigue dibujada)."""
    try:
        return fetch()
    except ApiError as error:
        if is_global(error):
            st.rerun()  # ejecución completa: `main.py` revisa el token y muestra A7 o A6
        show_staff_error(error)
        return None
