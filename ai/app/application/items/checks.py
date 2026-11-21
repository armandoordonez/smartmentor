"""Code checks of the item banks that go beyond ``contracts/validation.py`` (plan 5.4.4).

They run inside ``LlmRunner.run(check=...)``: a failed check sends the issues back to the model
(at most 2 retries) before the job ends with ``INVALID_OUTPUT``.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Collection, Mapping, Sequence

from app.domain.contracts.assessment import AssessmentItemLLM, AssessmentItemsLLM
from app.domain.contracts.common import ItemSource
from app.domain.contracts.validation import check_assessment_items, check_final_coverage

QUIZ_ID = re.compile(r"^q\d+$")
FINAL_ID = re.compile(r"^f(?P<n>\d+)_v(?P<k>\d+)$")
SIMILARITY_LIMIT = 0.85
_TOKEN = re.compile(r"\w+", re.UNICODE)


def _tokens(text: str) -> frozenset[str]:
    return frozenset(_TOKEN.findall(text.casefold()))


def stem_similarity(a: str, b: str) -> float:
    """Jaccard similarity of the words of two stems (1 = same words)."""
    left, right = _tokens(a), _tokens(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def repeated_stems(
    items: Sequence[AssessmentItemLLM], previous_stems: Collection[str]
) -> list[str]:
    """Items whose stem repeats (or barely rephrases) a stem that already exists in the bank."""
    return [
        f"{item.id}: the stem repeats an item that already exists in the bank"
        for item in items
        if any(stem_similarity(item.stem, old) >= SIMILARITY_LIMIT for old in previous_stems)
    ]


def check_quiz_bank(
    batch: AssessmentItemsLLM,
    *,
    topic_id: str,
    outcome_ids: Collection[str],
    n_multiple_choice: int,
    n_short_answer: int,
    previous_stems: Collection[str],
) -> list[str]:
    """Counts by type, ``q<n>`` ids, one topic, every outcome covered and stems not repeated."""
    issues = check_assessment_items(batch, {topic_id: set(outcome_ids)})
    items = batch.items
    kinds = Counter(i.item_type for i in items)
    if kinds["multiple_choice"] != n_multiple_choice:
        issues.append(
            f"{kinds['multiple_choice']} multiple-choice items (expected {n_multiple_choice})"
        )
    if kinds["short_answer"] != n_short_answer:
        issues.append(f"{kinds['short_answer']} short-answer items (expected {n_short_answer})")
    issues += [f"{i.id}: id must be q<n>" for i in items if not QUIZ_ID.match(i.id)]
    issues += [
        f"{i.id}: topic_id must be '{topic_id}' (got '{i.topic_id}')"
        for i in items
        if i.topic_id != topic_id
    ]
    covered = {i.outcome_id for i in items}
    if len(items) >= len(outcome_ids):
        issues += [f"outcome '{o}' has no item" for o in sorted(outcome_ids) if o not in covered]
    issues += [
        f"{i.id}: quiz items have no equivalence_group" for i in items if i.equivalence_group
    ]
    issues += repeated_stems(items, previous_stems)
    seen: list[AssessmentItemLLM] = []
    for item in items:
        if any(stem_similarity(item.stem, other.stem) >= SIMILARITY_LIMIT for other in seen):
            issues.append(f"{item.id}: the stem repeats another item of the batch")
        seen.append(item)
    return issues


def check_final_bank(
    batch: AssessmentItemsLLM,
    *,
    outcomes: Mapping[str, Collection[str]],
    path_topic_ids: Sequence[str],
    n_short_answer: int,
    n_versions: int,
    previous_stems: Collection[str],
) -> list[str]:
    """Parallel versions ``f<n>_v<k>`` with group ``eg_<n>``, coverage by topic and no repeats."""
    issues = check_assessment_items(batch, outcomes)
    issues += check_final_coverage(
        batch, path_topic_ids, short_answers=n_short_answer, versions=n_versions
    )
    versions_by_group: dict[str, set[int]] = {}
    for item in batch.items:
        match = FINAL_ID.match(item.id)
        if match is None:
            issues.append(f"{item.id}: id must be f<n>_v<k>")
            continue
        n, k = int(match["n"]), int(match["k"])
        if item.equivalence_group != f"eg_{n}":
            issues.append(f"{item.id}: equivalence_group must be eg_{n}")
        versions_by_group.setdefault(item.equivalence_group, set()).add(k)
    wanted = set(range(1, n_versions + 1))
    issues += [
        f"{group}: versions {sorted(found)} (expected 1..{n_versions})"
        for group, found in versions_by_group.items()
        if found != wanted
    ]
    by_group: dict[str, list[AssessmentItemLLM]] = {}
    for item in batch.items:
        by_group.setdefault(item.equivalence_group, []).append(item)
    for group, members in by_group.items():
        stems = [m.stem for m in members]
        if group and len({s.strip().casefold() for s in stems}) != len(stems):
            issues.append(f"{group}: parallel versions need different stems")
    issues += repeated_stems(batch.items, previous_stems)
    return issues


def final_source(item_id: str) -> ItemSource:
    """``f<n>_v1`` is the pre-test (``final``); the following versions are ``retention``."""
    match = FINAL_ID.match(item_id)
    return "final" if match is not None and int(match["k"]) == 1 else "retention"
