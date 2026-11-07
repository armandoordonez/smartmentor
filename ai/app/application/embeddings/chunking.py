"""Split a source document into fragments of about 900 characters (plan 5.4.7, ADR 0013).

As the Wizard of Oz notebook: paragraphs are the unit. Consecutive paragraphs are joined while the
fragment stays under the target; a paragraph longer than the target is cut at sentence ends (and,
as a last resort, at a word boundary), so no fragment is much longer than the target.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TARGET_CHARS = 900
CHARS_PER_TOKEN = 4

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    token_count: int


def _normalize(paragraph: str) -> str:
    return re.sub(r"[ \t]*\n[ \t]*", " ", paragraph).strip()


def _cut_long(paragraph: str, target: int) -> list[str]:
    """Cut a paragraph longer than ``target`` at sentence ends, then at word boundaries."""
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(paragraph):
        while len(sentence) > target:
            room = target - len(current) - 1 if current else target
            cut = sentence.rfind(" ", 0, max(room, 1))
            if cut <= 0:
                cut = min(target, len(sentence))
            head, sentence = sentence[:cut].strip(), sentence[cut:].strip()
            pieces.append(f"{current} {head}".strip() if current else head)
            current = ""
        if not sentence:
            continue
        if current and len(current) + 1 + len(sentence) > target:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def split_chunks(text: str, target: int = TARGET_CHARS) -> list[Chunk]:
    """Fragments of a document in reading order (empty paragraphs are dropped)."""
    paragraphs = [p for p in (_normalize(p) for p in _PARAGRAPH_BREAK.split(text)) if p]
    texts: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        for piece in _cut_long(paragraph, target) if len(paragraph) > target else [paragraph]:
            if buffer and len(buffer) + 2 + len(piece) > target:
                texts.append(buffer)
                buffer = piece
            else:
                buffer = f"{buffer}\n\n{piece}" if buffer else piece
    if buffer:
        texts.append(buffer)
    return [
        Chunk(index=i, text=t, token_count=max(1, len(t) // CHARS_PER_TOKEN))
        for i, t in enumerate(texts)
    ]
