"""Clean-up and option shuffling of freshly generated items (B-062).

Runs in code right after the LLM output passes its checks and before the automatic review, so
the review, the instructor and the learner all see the final text and order. It only touches the
banks generated from now on; the stored banks are never rewritten.

- ``clean_text`` removes stray Markdown emphasis (``**``, ``*word*``) outside inline code,
  turns escaped ``\\n`` into real line breaks and joins the lines into one, so the app (which
  wraps the stem in ``**...**`` and renders Markdown) never shows literal asterisks nor lines of a
  snippet glued together.
- ``shuffle_options`` reorders the four options with a seed derived from the item (topic, id and
  stem), not from the LLM: the same item always lands in the same order and the correct answer is
  spread over the four positions. ``correct_option`` and the option numbers or letters quoted in
  ``model_answer`` are remapped to the new order.
"""

from __future__ import annotations

import hashlib
import random
import re
from collections.abc import Callable, Sequence

from app.domain.contracts.assessment import (
    AssessmentItemLLM,
    AssessmentItemsLLM,
    RubricCriterionLLM,
)

_CODE_SPAN = re.compile(r"(`+)(.+?)\1", re.DOTALL)
_FENCE = re.compile(r"^\s*(```|~~~)")
_STRONG = re.compile(r"(?<![\w*])\*\*(?=\S)(.+?)(?<=\S)\*\*(?![\w*])")
# a ``**`` left alone, unless it sits between two operands (``x**2`` is a power, not emphasis)
_STRAY_STRONG = re.compile(r"(?<![\w)])\*{2,}|\*{2,}(?![\w(])")
_EMPHASIS = re.compile(r"(?<![\w*])\*(?=\S)([^*\n]*?\S)\*(?![\w*])")
_SPACES = re.compile(r"[ \t\u00a0\u2007\u202f]+")
_END_PUNCTUATION = (":", ".", ";", ",", "?", "!", "¿", "¡", "(")
LINE_SEPARATOR = "; "

# «opción 2», «la opción B», «las opciones 1 y 3», «opciones 0, 2 y 3» (the numbers or letters
# that follow are the positions the LLM used before the shuffle).
_OPTION_REFS = re.compile(
    r"(?P<word>\b[Oo]pci[oó]n(?:es)?\s+)"
    r"(?P<refs>(?:\d|[A-D])\b(?:\s*(?:,|\by\b|\be\b|\bo\b|\bu\b)\s*(?:\d|[A-D])\b)*)"
)
_REF_TOKEN = re.compile(r"\b(\d|[A-D])\b")
_CORRECT_REF = re.compile(r"\b[Oo]pci[oó]n\s+(\d)\b[^.]{0,40}?\bcorrecta\b")
_LETTERS = "ABCD"


def _outside_code(text: str, transform: Callable[[str], str]) -> str:
    """Apply ``transform`` only to the text outside inline code (`...`)."""
    parts: list[str] = []
    last = 0
    for match in _CODE_SPAN.finditer(text):
        parts.append(transform(text[last : match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(transform(text[last:]))
    return "".join(parts)


def _strip_emphasis(text: str) -> str:
    text = _STRONG.sub(r"\1", text)
    text = _STRAY_STRONG.sub("", text)
    return _EMPHASIS.sub(r"\1", text)


def _lines(text: str) -> list[str]:
    """Non-empty lines; the lines of a fenced code block become inline code."""
    lines: list[str] = []
    in_fence = False
    for raw in text.split("\n"):
        if _FENCE.match(raw):
            in_fence = not in_fence
            continue
        line = _SPACES.sub(" ", raw).strip()
        if not line:
            continue
        lines.append(f"`{line}`" if in_fence and "`" not in line else line)
    return lines


def _join(lines: Sequence[str]) -> str:
    """One line: a line that ends a sentence or opens a list is followed by a space, the rest
    (lines of a file, a command, a list) by ``LINE_SEPARATOR`` so they never read glued."""
    if not lines:
        return ""
    out = lines[0]
    for line in lines[1:]:
        out += (" " if out.endswith(_END_PUNCTUATION) else LINE_SEPARATOR) + line
    return out


def clean_text(text: str) -> str:
    """Plain one-line text: no stray Markdown emphasis, no escaped or glued line breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _outside_code(text, lambda part: part.replace("\\n", "\n"))
    text = _join(_lines(text))
    return _SPACES.sub(" ", _outside_code(text, _strip_emphasis)).strip()


def item_seed(item: AssessmentItemLLM) -> int:
    """Seed of one item: stable across runs and machines (no ``hash()``, no LLM)."""
    key = f"{item.topic_id}\x1f{item.id}\x1f{item.stem}".encode()
    return int.from_bytes(hashlib.sha256(key).digest()[:8], "big")


def _reference_base(model_answer: str, correct_option: int) -> int:
    """0 if the rationale numbers the options from 0 (the contract), 1 if it counts from 1."""
    for match in _CORRECT_REF.finditer(model_answer):
        quoted = int(match.group(1))
        if quoted == correct_option:
            return 0
        if quoted == correct_option + 1:
            return 1
    numbers = [int(n) for n in re.findall(r"\d", " ".join(_option_refs(model_answer)))]
    return 1 if numbers and max(numbers) >= len(_LETTERS) else 0


def _option_refs(text: str) -> list[str]:
    return [m.group("refs") for m in _OPTION_REFS.finditer(text)]


def remap_option_refs(text: str, new_position: Sequence[int], *, base: int) -> str:
    """Rewrite «opción N» / «opción X» so it points to the same option after the shuffle.

    ``new_position[old] = new``. Numbers keep their base (0 or 1) and letters stay letters.
    References out of range are left as they are.
    """

    def token(match: re.Match[str]) -> str:
        value = match.group(1)
        if value.isdigit():
            old = int(value) - base
            if 0 <= old < len(new_position):
                return str(new_position[old] + base)
            return value
        return _LETTERS[new_position[_LETTERS.index(value)]]

    def refs(match: re.Match[str]) -> str:
        return match.group("word") + _REF_TOKEN.sub(token, match.group("refs"))

    return _OPTION_REFS.sub(refs, text)


def shuffle_options(item: AssessmentItemLLM) -> AssessmentItemLLM:
    """The item with its options in a deterministic per-item order (multiple choice only)."""
    if item.item_type != "multiple_choice" or not 0 <= item.correct_option < len(item.options):
        return item
    order = list(range(len(item.options)))
    random.Random(item_seed(item)).shuffle(order)  # noqa: S311 - not security, only reproducible
    new_position = [order.index(old) for old in range(len(order))]
    base = _reference_base(item.model_answer, item.correct_option)
    return item.model_copy(
        update={
            "options": [item.options[old] for old in order],
            "correct_option": new_position[item.correct_option],
            "model_answer": remap_option_refs(item.model_answer, new_position, base=base),
        }
    )


def clean_item(item: AssessmentItemLLM) -> AssessmentItemLLM:
    """The item with clean stem, options, rationale and rubric (options kept if cleaning would
    make two of them equal, which the contract rejects)."""
    options = [clean_text(o) for o in item.options]
    if len({o.casefold() for o in options}) != len(options) or not all(options):
        options = list(item.options)
    return item.model_copy(
        update={
            "stem": clean_text(item.stem) or item.stem,
            "options": options,
            "model_answer": clean_text(item.model_answer),
            "rubric": [
                RubricCriterionLLM(
                    criterion=clean_text(c.criterion) or c.criterion, points=c.points
                )
                for c in item.rubric
            ],
        }
    )


def polish_items(batch: AssessmentItemsLLM) -> AssessmentItemsLLM:
    """Clean every item and shuffle the options of the multiple-choice ones."""
    return AssessmentItemsLLM(items=[shuffle_options(clean_item(i)) for i in batch.items])
