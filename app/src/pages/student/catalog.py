"""E1 · Catálogo de rutas."""

import streamlit as st

from components.course_card import render_path_card
from components.layout import render_page_header
from core.container import get_services
from core.navigation import DIAGNOSTIC, MY_PATH
from core.session import get_session

services = get_services()
session = get_session()
cards = services.catalog.list_path_cards()

render_page_header(
    "Rutas",
    caption="Elige una ruta. Primero harás un diagnóstico corto para saltar lo que ya dominas.",
)

if not cards:
    st.info("Todavía no hay rutas publicadas.")

for start in range(0, len(cards), 3):
    for column, card in zip(st.columns(3, gap="medium"), cards[start : start + 3], strict=False):
        with column:
            opened = render_path_card(card.path, enrolled=card.enrollment is not None)
        if not opened:
            continue
        if card.enrollment is None:
            session.start_onboarding(card.path.id)
            st.switch_page(DIAGNOSTIC)
        session.selected_path_id = card.path.id
        st.switch_page(DIAGNOSTIC if card.enrollment.status == "onboarding" else MY_PATH)
