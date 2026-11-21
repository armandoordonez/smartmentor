"""``verify_consistency``: cross-checks of the generated package (port of the notebook's idea).

Each contract is already valid on its own; these checks look across them: every topic has its
explanation, bank and video; the banks cover every learning outcome and share no stem; the
parallel versions of the final bank are complete; the gradings refer to real items.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from app.domain.contracts.assessment import AssessmentItemBank
from app.domain.contracts.content import TopicExplanation
from app.domain.contracts.grading import AnswerGrading
from app.domain.contracts.video import VideoResource
from app.ports.catalog import TopicRecord

_SPACES = re.compile(r"\s+")


@dataclass
class Package:
    topics: list[TopicRecord]
    explanations: dict[str, TopicExplanation] = field(default_factory=dict)
    quiz_banks: dict[str, AssessmentItemBank] = field(default_factory=dict)
    final_bank: AssessmentItemBank | None = None
    videos: dict[str, VideoResource] = field(default_factory=dict)
    gradings: list[AnswerGrading] = field(default_factory=list)
    failed_jobs: list[str] = field(default_factory=list)
    quiz_items_per_topic: int = 23
    final_versions: int = 2


def _stem(text: str) -> str:
    return _SPACES.sub(" ", text).strip().casefold()


def verify_consistency(package: Package) -> list[str]:
    issues = [f"job failed: {j}" for j in package.failed_jobs]
    known_items: set[str] = set()
    stems: Counter[str] = Counter()
    for topic in package.topics:
        explanation = package.explanations.get(topic.id)
        if explanation is None:
            issues.append(f"{topic.id}: no explanation")
        elif explanation.faithfulness is None:
            issues.append(f"{topic.id}: the explanation has no faithfulness")
        bank = package.quiz_banks.get(topic.id)
        if bank is None:
            issues.append(f"{topic.id}: no quiz bank")
        else:
            covered = {i.outcome_id for i in bank.items}
            issues += [
                f"{topic.id}: outcome {o.id} has no quiz item"
                for o in topic.outcomes
                if o.id not in covered
            ]
            if len(bank.items) != package.quiz_items_per_topic:
                issues.append(
                    f"{topic.id}: {len(bank.items)} quiz items "
                    f"(expected {package.quiz_items_per_topic})"
                )
            for item in bank.items:
                known_items.add(f"{topic.id}:{item.id}")
                stems[_stem(item.stem)] += 1
        video = package.videos.get(topic.id)
        if video is None:
            issues.append(f"{topic.id}: no video resource")
        elif video.origin == "none":
            issues.append(f"{topic.id}: no video candidates (the instructor must add one)")
    final = package.final_bank
    if final is None:
        issues.append("no final bank")
    else:
        groups: dict[str, list[str]] = {}
        for item in final.items:
            groups.setdefault(item.equivalence_group or "", []).append(item.source)
            stems[_stem(item.stem)] += 1
        for group, sources in groups.items():
            if len(sources) != package.final_versions:
                issues.append(
                    f"{group}: {len(sources)} versions (expected {package.final_versions})"
                )
            if sources.count("final") != 1:
                issues.append(f"{group}: must have exactly one final version")
        for topic in package.topics:
            if not any(i.topic_id == topic.id for i in final.items):
                issues.append(f"{topic.id}: no final item")
    issues += [f"repeated stem across banks: {s[:60]}" for s, n in stems.items() if n > 1]
    issues += [
        f"grading of unknown item {g.item_id}"
        for g in package.gradings
        if not any(k.endswith(f":{g.item_id}") for k in known_items)
    ]
    return issues
