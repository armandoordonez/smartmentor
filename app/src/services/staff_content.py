"""Revisión de contenido (D5, D5d) y videos (D5e): textos y armado del cuerpo a enviar.

Sin reglas de negocio: la fidelidad, el estado de revisión y la versión nueva los decide la API.
"""

from copy import deepcopy
from typing import Any

from clients.models_staff import Resource
from components.formatting import decimal, percent


def sources_text(resource: Resource) -> str:
    """«Apuntes unidad 3 · ISLR cap. 4» o «YouTube · relevancia 94 %»."""
    parts = list(resource.sources)
    if resource.relevance is not None:
        parts.append(f"relevancia {percent(resource.relevance)}")
    return " · ".join(parts) if parts else "—"


def faithfulness_text(resource: Resource) -> str:
    return "—" if resource.faithfulness is None else decimal(resource.faithfulness, 2)


def next_version(version: str) -> str:
    """«1.3» -> «1.4» (el contrato crea la versión `1.n+1` al editar)."""
    major, _, minor = version.partition(".")
    return f"{major}.{int(minor or 0) + 1}" if minor.isdigit() or not minor else version


def edited_content(
    content: dict[str, Any],
    *,
    sections: list[tuple[str, str]],
    summary: str,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Copia del `topic_explanation.v1` con las secciones, el resumen y las fuentes editadas."""
    result = deepcopy(content)
    result["sections"] = [{"heading": h, "body": b} for h, b in sections if h.strip() and b.strip()]
    result["summary"] = summary
    result["sources"] = sources
    return result


def video_minutes(seconds: int) -> str:
    return f"{max(1, round(seconds / 60))} min"
