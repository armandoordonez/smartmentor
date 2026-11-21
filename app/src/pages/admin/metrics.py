"""AD3 · Métricas globales de evaluación.

Las calcula la API en SQL (`GET /metrics/evaluation`); la página solo las muestra con su meta, su
prioridad y el tamaño de la muestra. Los fixtures marcan sus valores como de ejemplo.
"""

import streamlit as st

from clients.base import ApiError
from clients.models_staff import MetricEntry
from components.layout import render_notice, render_page_header
from components.staff_theme import METRIC_BADGE, PRIORITY_COLOR
from core.container import get_client
from core.staff_errors import show_staff_error
from services.staff_admin import metric_text

COLUMNS = 3

client = get_client()

render_notice("Solo Admin · Métricas de todo el sistema. El instructor solo ve las de sus rutas.")
CAPTION = "Metas orientativas del brief"

try:
    metrics = client.get_evaluation_metrics()
except ApiError as error:
    render_page_header("Métricas de evaluación", caption=CAPTION)
    show_staff_error(error)
    st.stop()
# La API real no tiene cohorte; los fixtures sí (Figma: «… · cohorte 2026-2»).
render_page_header(
    "Métricas de evaluación",
    caption=f"{CAPTION} · {metrics.cohort}" if metrics.cohort else CAPTION,
)
# Figma AD3 trae aquí «Configurar piloto»; el piloto se define fuera de la app (F-013) y el
# botón no se construye.
if metrics.is_sample_data:
    st.badge("Valores de ejemplo", color="orange")

if not metrics.groups:
    st.info("Todavía no hay métricas para mostrar.")
    st.stop()


def _card(metric: MetricEntry) -> None:
    label, color = METRIC_BADGE[metric.status]
    # `card-` toma la tarjeta blanca de layout.css; la prioridad a la izquierda y el estado a la
    # derecha, como en Figma AD3.
    with st.container(key=f"card-metric-{metric.code}"):
        with st.container(horizontal=True, horizontal_alignment="distribute"):
            st.badge(metric.priority, color=PRIORITY_COLOR.get(metric.priority, "gray"))
            st.badge(label, color=color)
        st.markdown(f"**{metric.name}**")
        st.markdown(f"### {metric_text(metric)}")
        st.caption(f"Meta: {metric.goal}")
        st.caption(metric.detail)


for group in metrics.groups:
    st.subheader(group.title, anchor=False)
    for start in range(0, len(group.metrics), COLUMNS):
        for column, metric in zip(
            st.columns(COLUMNS), group.metrics[start : start + COLUMNS], strict=False
        ):
            with column:
                _card(metric)
