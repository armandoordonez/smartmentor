"""Formato de números y fechas en español de Colombia, como en el diseño («92 %», «1,5»)."""

from datetime import date

_MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def percent(value: float) -> str:
    """Fracción (0 a 1) como porcentaje: 0,92 -> «92 %»."""
    return f"{round(value * 100)} %"


def percent_points(value: float) -> str:
    """Puntaje de 0 a 100 como porcentaje: 92,4 -> «92 %»."""
    return f"{round(value)} %"


def decimal(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def integer(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def usd(value: float, digits: int = 2) -> str:
    return f"US$ {decimal(value, digits)}"


def duration(minutes: int) -> str:
    """Minutos como «1 h 20 min», «8 h» o «45 min»."""
    hours, rest = divmod(minutes, 60)
    if not hours:
        return f"{rest} min"
    return f"{hours} h {rest} min" if rest else f"{hours} h"


def approx_duration(minutes: int) -> str:
    """Duración aproximada del catálogo: «~8 h», «~3 h 35 min»."""
    return f"~{duration(minutes)}"


def short_date(value: date) -> str:
    return f"{value.day} {_MONTHS[value.month - 1]} {value.year}"


def initials(full_name: str) -> str:
    parts = full_name.split()
    return "".join(p[0] for p in parts[:2]).upper() or "?"
