"""Pseudonymisation of the learner profile before it reaches the LLM (plan 5.4.12, DEF-05).

The API already sends the profile pseudonymised; this is the second barrier, with simple rules:
e-mail addresses, links, phone numbers and long digit sequences (``domain.pseudonymize``) plus
proper names introduced by a clear cue («me llamo Ana Gómez», «Soy Juan Pérez», «Dra. Pérez»,
«Atentamente, Luis Mora», ``@usuario``). A name with no cue is not detected: the rules trade
recall for few false positives in Spanish (a capitalised word is often a tool or a city).
"""

from __future__ import annotations

import re
from typing import Any

from app.domain.pseudonymize import pseudonymize

NAME_TAG = "[nombre]"
MAX_PROFILE_CHARS = 2000

_WORD = r"[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+"
_NAME = rf"{_WORD}(?:\s+(?:de\s+la\s+|de\s+los\s+|del\s+|de\s+|la\s+)?{_WORD}){{0,3}}"

_NAME_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    # «me llamo Ana Gómez», «mi nombre es Ana», «mi nombre completo es Ana Gómez»
    (
        re.compile(rf"(?i:\b(me\s+llamo|mi\s+nombre(?:\s+completo)?\s+es|me\s+dicen))\s+{_NAME}"),
        rf"\1 {NAME_TAG}",
    ),
    # «Soy Juan Pérez» (two or more capitalised words: «Soy Analista» is a role, not a name)
    (
        re.compile(
            rf"\b([Ss]oy)\s+{_WORD}\s+(?:(?:de\s+la\s+|del\s+|de\s+)?{_WORD})(?:\s+{_WORD}){{0,2}}"
        ),
        rf"\1 {NAME_TAG}",
    ),
    # Titles: «Dra. Pérez», «Ing. Carlos Ruiz»
    (
        re.compile(rf"\b(Sr|Sra|Srta|Dr|Dra|Ing|Lic|Prof|Mtro|Mtra)\.?\s+{_NAME}"),
        rf"\1. {NAME_TAG}",
    ),
    # Sign-offs: «Atentamente, Luis Mora»
    (
        re.compile(rf"(?i:\b(atentamente|cordialmente|saludos|gracias|un\s+abrazo)),?\s+{_NAME}"),
        rf"\1, {NAME_TAG}",
    ),
    # Handles: «@usuario»
    (re.compile(r"(?<![\w.])@[\w.]{2,}"), "[usuario]"),
)


def pseudonymize_profile(text: str, *, max_chars: int = MAX_PROFILE_CHARS) -> str:
    """The text with emails, phones, links and cued proper names replaced by tags, cut to size."""
    result = pseudonymize(text)
    for pattern, replacement in _NAME_RULES:
        result = pattern.sub(replacement, result)
    return result.strip()[:max_chars]


def pseudonymize_value(value: Any) -> Any:
    """Apply ``pseudonymize_profile`` to every string inside a JSON-like value."""
    if isinstance(value, str):
        return pseudonymize_profile(value)
    if isinstance(value, list):
        return [pseudonymize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: pseudonymize_value(v) for k, v in value.items()}
    return value
