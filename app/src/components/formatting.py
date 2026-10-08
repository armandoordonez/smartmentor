"""Formato de números y fechas en español de Colombia, como en el diseño («92 %», «1,5»)."""

from datetime import date

_MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def percent(value: float) -> str:
    return f"{round(value * 100)} %"


def decimal(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def integer(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def usd(value: float, digits: int = 2) -> str:
    return f"US$ {decimal(value, digits)}"


def duration(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    if not hours:
        return f"{rest} min"
    return f"{hours} h {rest} min" if rest else f"{hours} h"


def short_date(value: date) -> str:
    return f"{value.day} {_MONTHS[value.month - 1]} {value.year}"


def initials(full_name: str) -> str:
    parts = full_name.split()
    return "".join(p[0] for p in parts[:2]).upper() or "?"
