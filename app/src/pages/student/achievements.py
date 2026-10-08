"""E12 · Logros."""

import streamlit as st

from components.badge_card import render_badge_slot
from components.layout import render_page_header
from core.container import get_services
from core.navigation import BADGE
from core.session import get_session

services = get_services()
session = get_session()
slots = services.assessment.badge_slots()

render_page_header("Logros", caption="Tus badges digitales verificables.")

for start in range(0, len(slots), 2):
    for column, slot in zip(st.columns(2, gap="medium"), slots[start : start + 2], strict=False):
        with column:
            if render_badge_slot(slot.path, slot.badge, enrolled=slot.enrolled):
                session.selected_path_id = slot.path.id
                st.switch_page(BADGE)
