"""Revisión de contenido (D5, D5d) y videos (D5e): textos y armado del cuerpo a enviar.

Sin reglas de negocio: la fidelidad, el estado de revisión y la versión nueva los decide la API.
"""

import re
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


_YOUTUBE_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_MARKDOWN_LINK_TEXT = re.compile(r"([\\\[\]])")


def youtube_watch_url(video_id: str) -> str | None:
    """Enlace al video en YouTube; None si el identificador no tiene la forma de YouTube."""
    if not _YOUTUBE_VIDEO_ID.fullmatch(video_id):
        return None
    return f"https://www.youtube.com/watch?v={video_id}"


def youtube_thumbnail_url(video_id: str) -> str | None:
    """Portada (320 x 180) que YouTube publica de cada video; None si el id no sirve."""
    if not _YOUTUBE_VIDEO_ID.fullmatch(video_id):
        return None
    return f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"


def video_link_markdown(title: str, video_id: str) -> str:
    """El título como enlace a YouTube en Markdown (sin HTML); sin enlace si el id no sirve.

    El título viene de YouTube o del instructor: se escapan los corchetes y la barra invertida
    para que no rompa el enlace.
    """
    url = youtube_watch_url(video_id)
    if url is None:
        return title
    text = _MARKDOWN_LINK_TEXT.sub(r"\\\1", title)
    return f"[{text}]({url})"


def video_thumbnail_markdown(video_id: str) -> str | None:
    """La portada del video como imagen enlazada a YouTube, en Markdown (sin HTML)."""
    url, thumbnail = youtube_watch_url(video_id), youtube_thumbnail_url(video_id)
    if url is None or thumbnail is None:
        return None
    return f"[![Portada del video en YouTube]({thumbnail})]({url})"
