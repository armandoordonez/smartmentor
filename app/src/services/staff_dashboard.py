"""Ruta y avance (D3) y detalle del aprendiz (D4): textos y vistas a partir de la API.

Sin reglas de negocio: los umbrales, el estado de cada aprendiz y los temas críticos los calcula la
API; aquí solo se arman los textos. Las metas citadas son las del brief (secciones de métricas).
"""

from clients.models_staff import Dashboard, TopicStat
from components.formatting import decimal, percent

FIRST_ATTEMPT_GOAL = "entre 60 % y 85 %"
ATTEMPTS_GOAL = "hasta 1,8"


def settings_caption(dashboard: Dashboard) -> str:
    """«Ruta publicada · umbrales: tema 70 % · final 80 % · 3 intentos · omitir si … ≥ 80 %»."""
    s = dashboard.settings
    state = "Ruta publicada" if dashboard.published else "Ruta sin publicar"
    return (
        f"{state} · umbrales: tema {s.topic_pass_threshold} % · final {s.final_pass_threshold} % · "
        f"{s.max_attempts} intentos · omitir si diagnóstico ≥ {s.mastery_skip_threshold} %"
    )


def optional_percent(value: float | None) -> str:
    return "—" if value is None else percent(value)


def optional_decimal(value: float | None) -> str:
    return "—" if value is None else decimal(value)


def _count(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def critical_text(name: str, stat: TopicStat) -> str:
    """Una línea de «Temas críticos» con las metas del brief."""
    parts = [name]
    if stat.first_attempt_pass_rate is not None:
        parts.append(
            f"aprobación al primer intento {percent(stat.first_attempt_pass_rate)} "
            f"(meta del brief: {FIRST_ATTEMPT_GOAL})"
        )
    if stat.avg_attempts is not None:
        parts.append(f"{decimal(stat.avg_attempts)} intentos promedio (meta: {ATTEMPTS_GOAL})")
    parts.append(_count(stat.abandonments, "abandono", "abandonos"))
    return " · ".join(parts) + "."


def stat_by_topic(dashboard: Dashboard) -> dict[int, TopicStat]:
    return {stat.topic_id: stat for stat in dashboard.topic_stats}
