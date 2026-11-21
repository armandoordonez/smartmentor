"""Contenido de un tema (E6, E7b): convierte el `topic_explanation.v1` de la API en texto.

El texto viene de la IA y se muestra como Markdown sin HTML (`st.markdown`).
"""

from typing import Any

from clients.models import StepExplanation, StepVideo
from components.formatting import duration

SOURCE_NOTE = "Texto generado con IA a partir de fuentes verificadas y revisado por tu instructor"
ALTERNATE_NOTE = (
    "Explicación alterna generada con IA a partir de fuentes verificadas y revisada por tu "
    "instructor"
)


def explanation_text(content: dict[str, Any]) -> str:
    """Secciones del `topic_explanation.v1` como Markdown; el título solo si hay varias."""
    sections = [s for s in content.get("sections", []) if isinstance(s, dict)]
    parts = []
    for section in sections:
        body = str(section.get("body", "")).strip()
        heading = str(section.get("heading", "")).strip()
        parts.append(f"**{heading}**\n\n{body}" if heading and len(sections) > 1 else body)
    return "\n\n".join(part for part in parts if part)


def explanation_title(explanation: StepExplanation) -> str:
    return str(explanation.content.get("title", ""))


def source_note(explanation: StepExplanation, *, alternate: bool = False) -> str:
    base = ALTERNATE_NOTE if alternate else SOURCE_NOTE
    return f"{base} · prompt {explanation.prompt_version}"


def video_duration(video: StepVideo) -> str:
    return duration(max(round(video.duration_seconds / 60), 1))


def youtube_url(video: StepVideo) -> str:
    return f"https://www.youtube.com/watch?v={video.youtube_video_id}"
