"""Administración (AD1 a AD5, C4): textos y vistas a partir de la API, sin reglas de negocio.

Quién puede quedar sin rol de administrador, qué piloto está listo o qué inscripción sale del
análisis lo decide la API (`LAST_ADMIN`, `PILOT_NOT_READY`...).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from clients.models import Role
from clients.models_staff import AdminUser, LlmSummary, MetricEntry
from components.formatting import decimal, integer, usd
from components.staff_theme import ROLE_TEXT

_ROLE_ORDER: tuple[Role, ...] = ("admin", "instructor", "learner")


def ordered_roles(roles: Sequence[Role]) -> list[Role]:
    """Los roles del de mayor privilegio al de menor (admin, instructor, aprendiz)."""
    return [role for role in _ROLE_ORDER if role in roles]


def roles_text(roles: Sequence[Role]) -> str:
    """«Instructor, Aprendiz», del rol de mayor privilegio al de menor."""
    return ", ".join(ROLE_TEXT[role] for role in ordered_roles(roles)) or "—"


def users_caption(total: int, users: Sequence[AdminUser]) -> str:
    """«24 usuarios · 2 instructores · 1 admin», con los roles de la página cargada."""
    instructors = sum(1 for u in users if "instructor" in u.roles)
    admins = sum(1 for u in users if "admin" in u.roles)
    parts = [
        f"{total} usuarios",
        f"{instructors} {'instructor' if instructors == 1 else 'instructores'}",
        f"{admins} admin" if admins == 1 else f"{admins} admins",
    ]
    return " · ".join(parts)


@dataclass(frozen=True)
class LlmTotals:
    calls: str
    cost: str
    latency_p95: str
    invalid_json: str


def seconds(milliseconds: int) -> str:
    return f"{decimal(milliseconds / 1000)} s"


def metric_text(metric: MetricEntry) -> str:
    """Valor de una métrica de AD3: el texto de los fixtures o el número de la API con su unidad."""
    if metric.value_text:
        return metric.value_text
    value = metric.value
    if value is None:
        return "—"
    if metric.unit == "percent":
        points = value * 100
        return f"{decimal(points) if points < 10 else round(points)} %"
    if metric.unit == "seconds":
        return f"{decimal(value)} s"
    if metric.unit == "usd":
        return usd(value)
    if metric.unit == "minutes":
        return f"{round(value)} min"
    if metric.unit == "count":
        return integer(round(value))
    return decimal(value, 2)


def llm_totals(summary: LlmSummary) -> LlmTotals:
    """Totales del periodo: llamadas, costo, el p95 más alto por tarea y el JSON inválido."""
    calls = sum(t.calls for t in summary.by_task)
    invalid = sum(t.calls * t.invalid_json_rate for t in summary.by_task)
    worst_p95 = max((t.latency_p95_ms for t in summary.by_task), default=0)
    rate = (invalid / calls * 100) if calls else 0.0
    return LlmTotals(
        calls=integer(calls),
        cost=usd(summary.total_cost_usd),
        latency_p95=seconds(worst_p95),
        invalid_json=f"{decimal(rate)} %",
    )


def plural_learners(count: int) -> str:
    return f"{count} aprendiz" if count == 1 else f"{count} aprendices"
