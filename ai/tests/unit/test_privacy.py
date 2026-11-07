"""The profile is pseudonymised before it reaches the LLM (plan 5.4.12, DEF-05)."""

from __future__ import annotations

import pytest

from app.application.content.privacy import (
    MAX_PROFILE_CHARS,
    NAME_TAG,
    pseudonymize_profile,
    pseudonymize_value,
)


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        ("Escríbeme a ana.gomez@correo.com para lo que necesites.", "ana.gomez@correo.com"),
        ("Mi teléfono es +57 300 123 4567.", "300 123 4567"),
        ("Mi perfil: https://linkedin.com/in/anagomez", "linkedin.com"),
        ("Me llamo Ana María Gómez y trabajo en logística.", "Gómez"),
        ("Mi nombre es Carlos y uso Excel.", "Carlos"),
        ("Hola, soy Juan Pérez, analista de datos.", "Pérez"),
        ("Atentamente, Luis Mora", "Mora"),
        ("Consulta a la Dra. Ramírez sobre el tema.", "Ramírez"),
        ("Sígueme en @anagomez_ds", "anagomez_ds"),
    ],
)
def test_personal_data_is_removed(text: str, secret: str) -> None:
    assert secret not in pseudonymize_profile(text)


def test_names_are_replaced_by_a_tag_and_the_rest_of_the_text_is_kept() -> None:
    result = pseudonymize_profile("Me llamo Ana Gómez y trabajo en logística con SQL.")
    assert NAME_TAG in result
    assert "trabajo en logística con SQL" in result


def test_a_role_after_soy_is_not_a_name() -> None:
    text = "Soy analista de datos y uso Power BI en Bogotá."
    assert pseudonymize_profile(text) == text


def test_tools_and_cities_are_kept() -> None:
    text = "Trabajo con Excel, SQL y Power BI en Medellín."
    assert pseudonymize_profile(text) == text


def test_the_profile_is_cut_to_the_maximum_size() -> None:
    assert len(pseudonymize_profile("palabra " * 1000)) <= MAX_PROFILE_CHARS


def test_nested_values_are_pseudonymised() -> None:
    value = {"stem": "Contacto: a@b.co", "answers": ["Me llamo Pedro Pérez"], "n": 3}
    result = pseudonymize_value(value)
    assert "a@b.co" not in str(result)
    assert "Pérez" not in str(result)
    assert result["n"] == 3
