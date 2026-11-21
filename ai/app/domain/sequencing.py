"""Deterministic sequencing of the learning path (plan 5.4.8, brief P2). No LLM.

Rules (``docs/contracts/ai-service-v1.md``, 4.2):

* Topological order that keeps the syllabus ``position`` whenever the DAG allows it.
* Personalised arm: ``skipped`` (``skipped_mastered``) when level >= threshold and the topic is
  not mandatory. Fixed arm: every topic is included with ``fixed_path``.
* ``blocked`` when an included prerequisite is not completed (a skipped prerequisite counts as
  completed); otherwise ``pending``. So the first available step is always ``pending``.
* Inclusion reason by priority: ``mandatory`` > ``objective_focus`` > ``weak_prerequisite`` (it
  is a prerequisite of an included topic) > ``required_by_path``.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field

from app.domain.contracts.graph import find_cycle, topological_order
from app.domain.contracts.learning_path import (
    InclusionReason,
    LearningPath,
    PathStep,
    PilotArm,
    StepStatus,
)

ALGORITHM = "topological_threshold v1"


@dataclass(frozen=True)
class PathTopic:
    topic_id: str
    position: int
    prerequisites: list[str] = field(default_factory=list)
    is_mandatory: bool = False


class SequencingError(ValueError):
    """Invalid graph. ``code`` is ``PREREQUISITE_SELF`` or ``VALIDATION_ERROR``."""

    def __init__(self, code: str, message: str, cycle: list[str] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.cycle = cycle


def validate_graph(topics: Sequence[PathTopic]) -> None:
    ids = [t.topic_id for t in topics]
    if len(ids) != len(set(ids)):
        raise SequencingError("VALIDATION_ERROR", "a topic appears more than once")
    known = set(ids)
    for topic in topics:
        if topic.topic_id in topic.prerequisites:
            raise SequencingError(
                "PREREQUISITE_SELF", f"{topic.topic_id} cannot be its own prerequisite"
            )
        if unknown := sorted(set(topic.prerequisites) - known):
            raise SequencingError(
                "VALIDATION_ERROR", f"{topic.topic_id}: unknown prerequisites {unknown}"
            )
    cycle = find_cycle({t.topic_id: t.prerequisites for t in topics})
    if cycle:
        raise SequencingError("VALIDATION_ERROR", "prerequisite cycle", cycle=cycle)


def sequence_path(
    topics: Sequence[PathTopic],
    level_by_topic: Mapping[str, float],
    *,
    mastery_skip_threshold: float,
    focus_topic_ids: Collection[str] = (),
    pilot_arm: PilotArm | None = "personalized",
) -> LearningPath:
    if not topics:
        raise SequencingError("VALIDATION_ERROR", "the path has no topics")
    validate_graph(topics)
    by_id = {t.topic_id: t for t in topics}
    syllabus_order = [
        t.topic_id for _, t in sorted(enumerate(topics), key=lambda p: (p[1].position, p[0]))
    ]
    order = topological_order(syllabus_order, {t.topic_id: t.prerequisites for t in topics})

    fixed = pilot_arm == "fixed"
    skipped = {
        t
        for t in order
        if not fixed
        and not by_id[t].is_mandatory
        and t in level_by_topic
        and level_by_topic[t] >= mastery_skip_threshold
    }
    included = [t for t in order if t not in skipped]
    prerequisite_of_included = {p for t in included for p in by_id[t].prerequisites}
    focus = set(focus_topic_ids)

    steps: list[PathStep] = []
    for number, topic_id in enumerate(order, start=1):
        topic = by_id[topic_id]
        status: StepStatus
        reason: InclusionReason
        if topic_id in skipped:
            status, reason = "skipped", "skipped_mastered"
        else:
            waiting = any(p not in skipped for p in topic.prerequisites)
            status = "blocked" if waiting else "pending"
            if fixed:
                reason = "fixed_path"
            elif topic.is_mandatory:
                reason = "mandatory"
            elif topic_id in focus:
                reason = "objective_focus"
            elif topic_id in prerequisite_of_included:
                reason = "weak_prerequisite"
            else:
                reason = "required_by_path"
        steps.append(
            PathStep(
                step_order=number,
                topic_id=topic_id,
                status=status,
                inclusion_reason=reason,
                diagnostic_level=level_by_topic.get(topic_id),
            )
        )
    return LearningPath(
        algorithm=ALGORITHM,
        mastery_skip_threshold=mastery_skip_threshold,
        pilot_arm=pilot_arm,
        steps=steps,
    )
