"""A3b: el párrafo «Qué es el piloto» es una frase completa con y sin ventana (B-046)."""

import pytest

from components.consent_form import pilot_description


def test_pilot_description_with_window_capitalizes_it() -> None:
    text = pilot_description("entre el 2 y el 15 de noviembre de 2026")
    assert "Datos. Entre el 2 y el 15 de noviembre de 2026 evaluamos si" in text
    assert text.endswith("ayudan a aprender.")


@pytest.mark.parametrize("window", ["", "   "])
def test_pilot_description_without_window_is_a_complete_sentence(window: str) -> None:
    text = pilot_description(window)
    assert "Datos. En este piloto evaluamos si las rutas" in text
    assert "Datos. evaluamos" not in text
    assert "  " not in text
