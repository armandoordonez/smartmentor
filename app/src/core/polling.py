"""Sondeo de trabajos desde un `st.fragment`, con el vencimiento del token resuelto.

Los fragmentos se ejecutan fuera del `try/except` de `main.py`: un 401 dentro de ellos mostraba el
traceback de Streamlit en vez de A7 «Tu sesión expiró». Aquí un error global (401, 403 de rol) pide
una ejecución completa de la aplicación, que sí pasa por `main.py` y dibuja la pantalla de estado.
"""

from collections.abc import Callable

import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

from clients.base import ApiError
from clients.models import Job
from components import loading
from core.errors import is_global
from core.session import get_session
from core.staff_errors import show_staff_error
from core.staff_state import get_staff_state

# --- Modo espera (T-054) -------------------------------------------------------------------------
# Mientras una pantalla U1x espera un trabajo de IA, las lecturas que siguen (releer la inscripción
# o el diagnóstico al terminar) no dibujan «Cargando…» sobre la tarjeta de carga. El indicador es la
# clave de sesión `WAIT_MODE_KEY`, que guarda la página y el trabajo que se espera. Solo cuenta en
# esa página y mientras la sesión siga esperando ese trabajo (la página lo olvida al consumirlo),
# así un sondeo abandonado no calla los spinners del resto de la app.

WAIT_MODE_KEY = "wait_mode"
CREATING_ATTEMPT = "creating-attempt"
"""Marca del modo espera mientras el quiz pide el intento de un reintento (U1b, B-060)."""


def _current_page() -> str:
    ctx = get_script_run_ctx(suppress_warning=True)
    return ctx.page_script_hash if ctx is not None else ""


def enter_wait_mode(job_id: str) -> None:
    """Marca que la página actual espera el trabajo `job_id`: no se dibuja el spinner."""
    st.session_state[WAIT_MODE_KEY] = (_current_page(), job_id)


def leave_wait_mode() -> None:
    """Termina el modo espera (al navegar, reintentar o fallar el trabajo)."""
    st.session_state.pop(WAIT_MODE_KEY, None)


def in_wait_mode() -> bool:
    """Si la página actual está esperando un trabajo (hay un sondeo activo en la sesión)."""
    marked = st.session_state.get(WAIT_MODE_KEY)
    if marked is None:
        return False
    page, job_id = marked
    learner = get_session().learner
    if page != _current_page():
        return False
    if job_id == CREATING_ATTEMPT:
        return learner.pending_attempt is not None
    # La extracción del syllabus (D1c) es el trabajo que espera el instructor.
    return job_id in (learner.diagnostic_job_id, learner.quiz_job_id, get_staff_state().job_id)


loading.set_quiet_probe(in_wait_mode)


def poll_job_or_rerun(fetch: Callable[[], Job]) -> Job | None:
    """Devuelve el trabajo, o `None` si hubo un error ya mostrado (la página sigue dibujada)."""
    try:
        return fetch()
    except ApiError as error:
        if is_global(error):
            st.rerun()  # ejecución completa: `main.py` revisa el token y muestra A7 o A6
        show_staff_error(error)
        return None
