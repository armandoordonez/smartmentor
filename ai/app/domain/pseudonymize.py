"""Simple pseudonymisation of learner texts before they reach a provider (plan 5.4.12, DEF-05).

The API already sends pseudonymised texts; this is a second barrier with simple rules: e-mail
addresses, URLs, phone numbers and long digit sequences (document ids) are replaced by tags.
Proper names are not detected here (too many false positives in Spanish): that stays with the
API, which never sends the learner's name.
"""

from __future__ import annotations

import re

_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[correo]"),
    (re.compile(r"\bhttps?://\S+|\bwww\.\S+", re.IGNORECASE), "[enlace]"),
    (re.compile(r"(?<!\w)\+?\d[\d\s().-]{6,}\d(?!\w)"), "[número]"),
)


def pseudonymize(text: str) -> str:
    for pattern, tag in _RULES:
        text = pattern.sub(tag, text)
    return text
