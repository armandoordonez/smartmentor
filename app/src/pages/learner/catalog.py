"""E1 · Catálogo de rutas.

«Ver ruta» inscribe a la persona (`POST /me/enrollments`) o retoma su inscripción y navega por el
`next_action` que devuelve la API; la interfaz no deduce a qué pantalla ir.
"""

import streamlit as st

from clients.base import ApiError
from clients.models import Enrollment
from components.course_card import PathCardView, render_path_card
from components.layout import render_page_header
from core.container import get_client
from core.errors import show_action_error
from core.navigation import SCREEN_PAGES, page_for_next_action
from core.session import get_session
from services.catalog import load_catalog, open_path

COLUMNS = 3  # máximo de columnas (app/CLAUDE.md, sección 7: responsive)

session = get_session()
client = get_client()


def _render_cards(cards: list[PathCardView]) -> int | None:
    """Dibuja las tarjetas en filas de tres y devuelve la ruta cuyo botón se pulsó."""
    chosen: int | None = None
    for start in range(0, len(cards), COLUMNS):
        row = cards[start : start + COLUMNS]
        for column, card in zip(st.columns(COLUMNS), row, strict=False):
            with column:
                if render_path_card(card):
                    chosen = card.path_id
    return chosen


# Con la ruta ya armada, abrirla desde el catálogo muestra la ruta (E5) y no salta al paso abierto:
# antes, con un quiz empezado, «Ver ruta» llevaba siempre al quiz (B-023). Mientras falte el
# perfil, el diagnóstico o el objetivo, se sigue el `next_action`.
IN_PATH_STATUSES = frozenset({"in_path", "final_ready", "completed"})


def _go_to(enrollment: Enrollment) -> None:
    session.start_onboarding(enrollment.learning_path.id, enrollment.id)
    if enrollment.status in IN_PATH_STATUSES:
        st.switch_page(SCREEN_PAGES["E5"])
    target = page_for_next_action(enrollment.next_action)
    if target is None:
        st.info(
            f"Te inscribiste en «{enrollment.learning_path.name}». "
            "La pantalla que sigue llega en la siguiente parte de la interfaz."
        )
        return
    st.switch_page(target)


render_page_header(
    "Rutas",
    caption="Elige una ruta. Primero harás un diagnóstico corto para saltar lo que ya dominas.",
)

try:
    catalog = load_catalog(client)
except ApiError as error:
    show_action_error(error)
    st.stop()

if catalog.is_empty:
    st.info("Todavía no hay rutas publicadas.")
    st.stop()

selected = _render_cards(catalog.paths)
if catalog.applied_ai:
    st.subheader("Rutas de IA aplicada", anchor=False)
    st.caption(
        "Rutas cortas para usar asistentes de IA en el trabajo. Cada una empieza con tu perfil, "
        "tu hoja de vida si aún no la tienes y un diagnóstico."
    )
    selected = _render_cards(catalog.applied_ai) or selected

if selected is not None:
    try:
        _go_to(open_path(client, selected))
    except ApiError as error:
        show_action_error(error)
