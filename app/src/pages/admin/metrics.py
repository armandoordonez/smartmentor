"""AD3 · Métricas globales de evaluación, con las metas del brief."""

import streamlit as st

from clients.models import EvaluationMetric
from components.formatting import decimal, integer, usd
from components.kpi_cards import render_metric_card
from components.layout import render_notice, render_page_header
from components.theme import TARGET_BADGE, BadgeColor
from core.container import get_services

services = get_services()
metrics = services.admin.metrics()


def formatted(metric: EvaluationMetric, value: float) -> str:
    match metric.unit:
        case "ratio":
            return decimal(value, 2)
        case "score":
            return integer(round(value))
        case "count":
            return decimal(value, 1)
        case "usd":
            return usd(value)


render_notice("Solo Admin · Métricas de todo el sistema. El docente solo ve las de sus rutas.")
render_page_header(
    "Métricas de evaluación", caption="Metas orientativas del brief · cohorte 2026-2"
)

for start in range(0, len(metrics), 3):
    for column, view in zip(st.columns(3, gap="medium"), metrics[start : start + 3], strict=False):
        metric = view.metric
        color: BadgeColor
        if metric.target is None or view.meets_target is None:
            badge, color = "Reportar", "gray"
        else:
            sign = "≥" if metric.comparison == "gte" else "≤"
            badge = f"Meta {sign} {formatted(metric, metric.target)}"
            color = TARGET_BADGE[view.meets_target]
        with column:
            render_metric_card(formatted(metric, metric.value), metric.label, badge, color)
