"""E12 · Logros: los badges obtenidos y las rutas que aún los bloquean.

Los badges salen de `GET /me/badges`; «Ver badge» abre E10 con la verificación pública. Las rutas
sin badge se muestran bloqueadas con lo que falta.
"""

import streamlit as st

from clients.base import ApiError
from components.badge_card import render_badge_slot
from components.formatting import short_date
from components.layout import render_page_header
from components.theme import ENROLLMENT_BADGE
from core.container import get_client
from core.errors import show_action_error
from core.session import get_session

BADGE_PAGE = "pages/learner/badge.py"

client = get_client()
session = get_session()

render_page_header("Logros", caption="Tus badges digitales: imagen PNG + archivo JSON Open Badges.")

try:
    badges = client.list_badges()
    catalog = client.list_learning_paths(limit=100)
    enrollments = client.list_enrollments(limit=100).items
except ApiError as error:
    show_action_error(error)
    st.stop()

names = {badge.learning_path_name for badge in badges}
# Rejilla de dos columnas, como en Figma: primero los badges obtenidos y luego los demás.
slots: list[tuple[str, str, bool, str, str | None, int | None]] = [
    (
        badge.learning_path_name,
        f"Obtenido {short_date(badge.issued_at.date())}" if badge.issued_at else "Obtenido",
        True,
        badge.public_id,
        "Ver badge",
        badge.enrollment_id,
    )
    for badge in badges
]
enrolled = {e.learning_path.id: e for e in enrollments}
for card in catalog.items:
    if card.name in names:
        continue
    enrollment = enrolled.get(card.id)
    if enrollment is None:
        caption = "Bloqueado · inscríbete para obtenerlo"
    else:
        # Inscrita pero sin badge: el estado y el avance de esa ruta, con los textos de E11 (B-037).
        caption = ENROLLMENT_BADGE[enrollment.status][0]
        if enrollment.progress.steps_total:
            progress = enrollment.progress
            caption += f" · {progress.steps_done} de {progress.steps_total} temas aprobados"
    slots.append((card.name, caption, False, f"path-{card.id}", None, None))
for start in range(0, len(slots), 2):
    for column, (name, caption, obtained, key, action, enrollment_id) in zip(
        st.columns(2), slots[start : start + 2], strict=False
    ):
        with column:
            if render_badge_slot(name, caption, obtained=obtained, key=key, action_label=action):
                session.selected_enrollment_id = enrollment_id
                st.switch_page(BADGE_PAGE)
