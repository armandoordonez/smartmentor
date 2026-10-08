from datetime import date

from components.formatting import decimal, duration, initials, integer, percent, short_date, usd


def test_numbers_use_the_design_format() -> None:
    assert percent(0.92) == "92 %"
    assert decimal(1.5) == "1,5"
    assert integer(1284) == "1.284"
    assert usd(4.12) == "US$ 4,12"


def test_duration_and_dates() -> None:
    assert duration(80) == "1 h 20 min"
    assert duration(45) == "45 min"
    assert duration(120) == "2 h"
    assert short_date(date(2026, 10, 5)) == "5 oct 2026"
    assert initials("Laura Martínez") == "LM"
