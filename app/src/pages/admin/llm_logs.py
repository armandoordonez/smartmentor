"""AD2 · Log del LLM y costos.

Resumen (`GET /llm-call-logs/summary`) y últimas llamadas (`GET /llm-call-logs`). El log contiene
prompts y costos: solo el administrador lo ve; el instructor ve las métricas de sus rutas (AD3).
"""

import streamlit as st

from clients.base import ApiError
from components.formatting import integer, usd
from components.kpi_cards import Kpi, render_kpis
from components.layout import render_notice, render_page_header
from components.table import Row, render_table
from components.theme import AI_TASK_LABEL
from core.container import get_client
from core.staff_errors import show_staff_error
from core.staff_state import PROMPT_CATALOG
from services.staff_admin import llm_totals, seconds

PAGE_SIZE = 50

client = get_client()

render_notice(
    "Solo Admin · El log contiene prompts y costos. El instructor solo ve métricas de sus rutas."
)
render_page_header("Log LLM y costos", caption="Últimos 7 días")

limit = int(st.session_state.get("ll-limit", PAGE_SIZE))
try:
    summary = client.get_llm_summary()
    logs = client.list_llm_logs(limit=limit)
except ApiError as error:
    show_staff_error(error)
    st.stop()

totals = llm_totals(summary)
render_kpis(
    [
        Kpi("calls", "Llamadas", totals.calls),
        Kpi("cost", "Costo total", totals.cost),
        Kpi("latency", "Latencia p95", totals.latency_p95),
        Kpi("invalid", "JSON inválido", totals.invalid_json),
    ]
)

rows = [
    Row(
        key=str(log.id),
        cells=[
            f"**{AI_TASK_LABEL.get(log.task_label, log.task_label)}**",
            log.model or "—",
            f"{log.prompt_id} {log.prompt_version}".strip() or "—",
            integer(log.tokens),
            usd(log.cost_usd, 3),
            seconds(log.latency_ms),
        ],
    )
    for log in logs.items
]
render_table(
    ["Tarea", "Modelo", "Prompt", "Tokens", "Costo", "Latencia"],
    [3, 2, 3, 1, 1, 1],
    rows,
    key="llm-logs",
    empty_text="Todavía no hay llamadas registradas.",
)
if logs.total > len(logs.items):
    st.caption(f"Mostrando {len(logs.items)} de {logs.total} llamadas.")
    if st.button("Ver más", key="ll-more"):
        st.session_state["ll-limit"] = limit + PAGE_SIZE
        st.rerun()
if st.button(
    "Ver el catálogo de prompts y versiones (documentación del equipo)",
    type="tertiary",
    key="ll-catalog",
):
    st.switch_page(PROMPT_CATALOG)
