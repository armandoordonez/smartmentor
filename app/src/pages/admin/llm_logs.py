"""AD2 · Admin · Log LLM y costos."""

from components.formatting import decimal, integer, usd
from components.kpi_cards import render_kpis
from components.layout import render_notice, render_page_header
from components.table import Row, render_table
from core.container import get_services

services = get_services()
log = services.admin.llm_log()

render_notice(
    "Solo Admin · El log contiene prompts y costos. El docente solo ve métricas de sus rutas."
)
render_page_header("Log LLM y costos", caption=f"Últimos {log.period_days} días")
render_kpis(
    [
        (integer(log.calls), "Llamadas"),
        (usd(log.total_cost_usd), "Costo total"),
        (f"{decimal(log.p95_latency_seconds)} s", "Latencia p95"),
        (f"{decimal(log.invalid_json_rate * 100)} %", "JSON inválido"),
    ]
)
render_table(
    ["Tarea", "Modelo", "Prompt", "Tokens", "Costo", "Latencia"],
    [2, 1.4, 1.8, 0.8, 0.9, 0.8],
    [
        Row(
            key=str(i),
            cells=[
                call.task,
                call.model,
                f"`{call.prompt_version}`",
                integer(call.tokens),
                usd(call.cost_usd, 3),
                f"{decimal(call.latency_seconds)} s",
            ],
        )
        for i, call in enumerate(log.recent)
    ],
    key="llm-calls",
)
