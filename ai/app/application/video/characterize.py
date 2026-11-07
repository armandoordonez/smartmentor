"""Characterisation of a video by its metadata against the closed list of subtopics (plan 4.2).

The report asks for the concepts of the topic that a video covers, from a closed list and with
evidence. Without captions (DEF-07) the evidence is the title, description and chapters: a
subtopic counts as covered when every significant word of it appears in that text. The result is
the ``characterization`` of the candidate and the text that is embedded for the similarity.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

from app.ports.video import Transcript, VideoSearchHit

MAX_EMBED_CHARS = 1500
MIN_WORD_CHARS = 4
STEM_CHARS = 6  # «regresión» and «regresiones» share the stem «regres»

_WORD = re.compile(r"[a-z0-9]+")


def normalize(text: str) -> str:
    """Lower case without accents (``Regresión`` -> ``regresion``)."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _stems(text: str) -> set[str]:
    return {w[:STEM_CHARS] for w in _WORD.findall(normalize(text))}


def covered_subtopics(subtopics: Sequence[str], evidence: str) -> list[str]:
    """Subtopics of the closed list whose significant words all appear in the evidence."""
    available = _stems(evidence)
    covered: list[str] = []
    for subtopic in subtopics:
        words = [w for w in _WORD.findall(normalize(subtopic)) if len(w) >= MIN_WORD_CHARS]
        words = words or _WORD.findall(normalize(subtopic))
        if words and all(w[:STEM_CHARS] in available for w in words):
            covered.append(subtopic)
    return covered


def video_embedding_text(
    hit: VideoSearchHit, transcript: Transcript, covered: Sequence[str]
) -> str:
    """Text embedded for the similarity: title, covered subtopics and the metadata text."""
    parts = [hit.title]
    if covered:
        parts.append("Subtemas: " + ", ".join(covered) + ".")
    parts.append(transcript.text)
    return " ".join(p for p in parts if p).strip()[:MAX_EMBED_CHARS]
