"""Compara los textos y el orden de una página con la especificación de Figma v3.

Lee `design/03-prototipo-alta-fidelidad/v3/estructura-pantallas.json` (textos del frame, en orden de
lectura, sin el menú superior) y comprueba que **todos** aparecen en la página en ese orden. Una
diferencia aceptada se declara en la prueba con su motivo; si el archivo no existe (la imagen de
Docker no lo trae), la prueba se omite.
"""

import json
import re
from functools import cache
from typing import Any

import pytest
from apptest import plain
from support import REPO_ROOT

SPEC = REPO_ROOT / "design" / "03-prototipo-alta-fidelidad" / "v3" / "estructura-pantallas.json"
_LEADING_MARKS = re.compile(r"^(?:☐|✓|\+)\s*")
_TRAILING_ARROW = re.compile(r"\s*▾$")


@cache
def _screens() -> dict[str, dict[str, Any]]:
    if not SPEC.is_file():
        pytest.skip("No está la especificación de Figma v3 (design/03-prototipo-alta-fidelidad/v3)")
    data = json.loads(SPEC.read_text(encoding="utf-8"))
    return {screen["name"].split(" ·")[0].strip(): screen for screen in data["pantallas"]}


def _collect(node: dict[str, Any], out: list[str]) -> None:
    if node.get("cmp", "").startswith("Menú superior"):
        return
    if node.get("t") == "T":
        out.append(node.get("c", ""))
    for child in node.get("ch", []):
        _collect(child, out)


def figma_texts(screen: str, *, skip_brand: bool = False) -> list[str]:
    """Textos del frame en orden de lectura, normalizados como los de la página.

    `skip_brand` quita la marca «SmartMentor» de la fila superior (A3b y A3c la dibujan como
    texto suelto; en la app es la barra superior).
    """
    texts: list[str] = []
    _collect(_screens()[screen]["raiz"], texts)
    result = []
    for text in texts:
        text = _TRAILING_ARROW.sub("", _LEADING_MARKS.sub("", plain(text)))
        if text:
            result.append(text)
    if skip_brand and result and result[0] == "SmartMentor":
        result = result[1:]
    return result


def missing_in_order(expected: list[str], rendered: list[str]) -> list[str]:
    """Textos de Figma que no aparecen en la página, buscados en orden (contenidos en un texto)."""
    missing: list[str] = []
    position = 0
    for text in expected:
        for index in range(position, len(rendered)):
            if text in rendered[index]:
                position = index
                break
        else:
            missing.append(text)
    return missing
