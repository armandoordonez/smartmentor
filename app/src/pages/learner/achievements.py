"""E12 · Logros: los badges obtenidos y las rutas que aún los bloquean.

Los badges salen de `GET /me/badges`; «Ver badge» abre E10 con la verificación pública. Las rutas sin
badge se muestran bloqueadas con lo que falta.
"""

import streamlit as st

from clients.base import ApiError
from components.badge_card import render_badge_slot
from components.formatting import short_date
from components.layout import render_page_header
from core.container import get_client
from core.errors import show_action_error
from core.session import get_session

BADGE_PAGE = "pages/learner/badge.py"

client = get_client()
session = get_session()

render_page_header(
    "Logros", caption="Tus badges digitales: imagen PNG + archivo JSON Open Badges."
)

try:
    badges = client.list_badges()
    catalog = client.list_learning_paths(limit=100)
except ApiError as error:
    show_action_error(error)
    st.stop()

names = {badge.learning_path_name for badge in badges}
for badge in badges:
    with st.container(key=f"achievement-{badge.public_id}"):
        render_badge_slot(
            badge.learning_path_name,
            f"Obtenido {short_date(badge.issued_at.date())}",
            obtained=True,
            key=badge.public_id,
        )
        if st.button("Ver badge", key=f"view-badge-{badge.public_id}"):
            session.selected_enrollment_id = badge.enrollment_id
            st.switch_page(BADGE_PAGE)

for card in catalog.items:
    if card.name not in names:
        render_badge_slot(
            card.name,
            "Bloqueado · inscríbete para obtenerlo",
            obtained=False,
            key=f"path-{card.id}",
        )
