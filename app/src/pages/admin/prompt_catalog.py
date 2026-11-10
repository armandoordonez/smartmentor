"""C4 · Catálogo de prompts y versiones (documentación del equipo, P2).

Muestra el catálogo de `prompts/catalog.yaml`. No hay ruta de la API para leerlo: es documentación
del prototipo, así que la lista vive en `services/staff_prompts.py`.
"""

import streamlit as st

from components.layout import render_page_header
from components.table import Row, render_table
from core.staff_state import LLM_LOGS
from services.staff_prompts import PROMPTS

render_page_header(
    "Catálogo de prompts y versiones",
    breadcrumb="Documentación del prototipo",
    caption=(
        "Nombres únicos para el repositorio (prompts/) y para las pantallas. Formato de versión: "
        "v1, v2… El prompt y su versión se registran en el Log LLM de cada llamada."
    ),
)
rows = [
    Row(
        key=prompt.prompt_id,
        cells=[
            f"**{prompt.prompt_id} v{prompt.version}**",
            prompt.name,
            prompt.screens or "—",
            ("En repositorio", "green"),
        ],
    )
    for prompt in PROMPTS
]
render_table(
    ["Prompt", "Qué hace", "Pantallas", "Estado"],
    [3, 4, 2, 2],
    rows,
    key="prompts",
    empty_text="No hay prompts registrados.",
)
if st.button("Volver al Log LLM", key="c4-back"):
    st.switch_page(LLM_LOGS)
