"""Video del tema según el inglés del aprendiz (E6; R-001).

La colecta de `ai/` es por tema y la comparte todo el curso: ordena con el inglés como respaldo
(penalizado frente al español), así que el video `in_use` ya es el que vería quien entiende
inglés. Quien declara inglés B1 o superior en la hoja de vida (`user_profiles.languages`) recibe
ese video tal cual. A quien no lo declara, si el video del tema está en inglés, la API le pide a
`ai/` que reordene los videos del tema (`in_use` y respaldos) con `video.rank` y
`preferences.english_allowed = false`. Si ninguno queda o `ai/` no responde, se conserva el video
del tema: es mejor un video en inglés que ninguno.
"""

import logging
import re
from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError

from app.domains.ai_gateway.exceptions import (
    AiBudgetExceededError,
    AiServiceUnavailableError,
    AiTaskFailedError,
)
from app.domains.ai_gateway.repository import AiServicePort
from app.domains.content.contracts import VideoResourceV1

logger = logging.getLogger(__name__)

VIDEO_RANK = "video.rank"
ENGLISH_MIN_LEVELS = frozenset({"B1", "B2", "C1", "C2"})
PREFERRED_LANGUAGE = "es"
WATCH_URL = "https://www.youtube.com/watch?v={video_id}"
_CHARACTERIZATION_SOURCES = frozenset({"metadata", "transcript", "instructor"})
_PUBLIC_FIELDS = ("video_candidate_id", "youtube_video_id", "title", "duration_seconds")


def english_allowed(languages: Sequence[Any] | None) -> bool:
    """`True` si la hoja de vida declara inglés (`en`, `en-US`…) con nivel B1 o superior."""
    for item in languages or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip().lower().replace("_", "-")
        level = str(item.get("cefr_level") or "").strip().upper()
        if code.split("-")[0] == "en" and level in ENGLISH_MIN_LEVELS:
            return True
    return False


def language_code(value: str | None) -> str | None:
    """Código de dos letras («es-419» → «es»), o `None` si no se reconoce."""
    code = (value or "").strip().lower()[:2]
    return code if re.fullmatch(r"[a-z]{2}", code) else None


def public_video(video: dict[str, Any]) -> dict[str, Any]:
    """Lo que ve el aprendiz en E6 (`StepContent.video`)."""
    return {k: video[k] for k in _PUBLIC_FIELDS} | {"is_backup": video["status"] == "backup"}


def rank_input(
    topic_id: int, videos: Sequence[dict[str, Any]], *, allow_english: bool
) -> dict[str, Any]:
    """Cuerpo de `POST /v1/tasks/video.rank` (contrato `ai-service-v1`, sección 4.3)."""
    return {
        "topic_id": str(topic_id),
        "candidates": [
            {
                "youtube_video_id": v["youtube_video_id"],
                "title": v["title"],
                "url": WATCH_URL.format(video_id=v["youtube_video_id"]),
                "channel": v.get("channel") or "",
                "origin": v.get("origin") or "youtube_api",
                "duration_seconds": v.get("duration_seconds"),
                "language": language_code(v.get("language")),
                "has_captions": v.get("has_captions"),
                "characterization": v.get("characterization"),
                "characterization_source": (
                    v.get("characterization_source")
                    if v.get("characterization_source") in _CHARACTERIZATION_SOURCES
                    else None
                ),
                "similarity": (float(v["similarity"]) if v.get("similarity") is not None else None),
            }
            for v in videos
        ],
        "preferences": {"language": PREFERRED_LANGUAGE, "english_allowed": allow_english},
    }


async def pick_video(
    ai: AiServicePort,
    topic_id: int,
    videos: Sequence[dict[str, Any]],
    *,
    allow_english: bool,
) -> dict[str, Any] | None:
    """El video que ve este aprendiz: el del tema o, si no lo entiende, el que elija `video.rank`.

    `videos` viene ordenado como lo sirve la API (`in_use` primero, luego los respaldos).
    """
    if not videos:
        return None
    current = videos[0]
    if allow_english or language_code(current.get("language")) != "en":
        return public_video(current)
    try:
        raw = await ai.run_task(VIDEO_RANK, rank_input(topic_id, videos, allow_english=False))
        selected = VideoResourceV1.model_validate(raw).selected_video_id
    except (
        AiServiceUnavailableError,
        AiBudgetExceededError,
        AiTaskFailedError,
        ValidationError,
    ) as exc:
        logger.warning(
            "video.rank unavailable; keeping the topic video",
            extra={"topic_id": topic_id, "error": type(exc).__name__},
        )
        return public_video(current)
    chosen = next((v for v in videos if v["youtube_video_id"] == selected), None)
    return public_video(chosen or current)
