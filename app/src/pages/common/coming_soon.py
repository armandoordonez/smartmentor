"""Marcador de las pantallas que se construyen en las siguientes partes de la Fase 7."""

import streamlit as st

from components.layout import render_page_header

render_page_header(
    "Próximamente",
    caption="Esta sección todavía no está disponible en esta versión de la interfaz.",
)
st.info("Mientras tanto puedes usar el menú superior o volver al inicio.")
