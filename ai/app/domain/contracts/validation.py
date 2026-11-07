"""Code checks on LLM outputs that a JSON Schema cannot express (plan 5.4.4).

Pipeline per call: provider structured output -> ``Model.model_validate_json`` -> the
``check_*`` function of this module -> on issues, retry with the issues in the prompt
(at most 2 retries) -> ``invalid_output``. Each function returns the list of issues found
(empty = valid) so the caller can log them and feed them back to the model.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Collection, Mapping, Sequence

from app.domain.contracts.assessment import (
    RUBRIC_MAX_CRITERIA,
    RUBRIC_MIN_CRITERIA,
    RUBRIC_POINTS_TOLERANCE,
    AssessmentItemLLM,
    AssessmentItemsLLM,
    ItemReviewLLM,
    RubricCriterion,
    SimulatedAnswersLLM,
)
from app.domain.contracts.badge import MAX_COMPETENCIES, MIN_COMPETENCIES, BadgeTextLLM
from app.domain.contracts.common import (
    MULTIPLE_CHOICE_OPTIONS,
    SNAKE_CASE,
    BloomLevel,
    ItemType,
    bloom_rank,
    cited_numbers,
)
from app.domain.contracts.content import (
    MAX_CLAIMS,
    FaithfulnessCheckLLM,
    PersonalizedExampleLLM,
    TopicExplanationLLM,
)
from app.domain.contracts.diagnostic import ObjectiveLLM
from app.domain.contracts.grading import POINTS_TOLERANCE, ShortAnswerGradingLLM
from app.domain.contracts.graph import find_cycle
from app.domain.contracts.syllabus import SyllabusLLM

MIN_OUTCOMES_PER_TOPIC = 2
MAX_OUTCOMES_PER_TOPIC = 4
REFLECTION_QUESTIONS = 2
SECTION_RANGE = {"main": (3, 5), "remedial": (2, 4)}
DIAGNOSTIC_PATTERN: tuple[tuple[BloomLevel, int], ...] = (
    ("remember", 1),
    ("apply", 2),
    ("analyze", 3),
)
FINAL_MC_PER_TOPIC = 2
MAX_DIFFICULTY = 3

OutcomesByTopic = Mapping[str, Collection[str]]


class ContractCheckError(ValueError):
    """Raised by ``ensure_valid`` when a check found issues."""

    def __init__(self, issues: Sequence[str]) -> None:
        self.issues = list(issues)
        super().__init__("; ".join(self.issues))


def ensure_valid(issues: Sequence[str]) -> None:
    if issues:
        raise ContractCheckError(issues)


def _duplicates(values: Sequence[str]) -> list[str]:
    return sorted(v for v, n in Counter(values).items() if n > 1)


# ---------- Syllabus ----------


def check_syllabus(syllabus: SyllabusLLM) -> list[str]:
    """Unique snake_case ids, existing prerequisites, DAG without cycles, outcome ids."""
    issues: list[str] = []
    if not SNAKE_CASE.match(syllabus.course_key):
        issues.append(f"course_key '{syllabus.course_key}' is not snake_case")
    if not syllabus.topics:
        return [*issues, "the syllabus has no topics"]
    ids = [t.id for t in syllabus.topics]
    issues += [f"duplicated topic id '{d}'" for d in _duplicates(ids)]
    known = set(ids)
    outcome_ids: list[str] = []
    for topic in syllabus.topics:
        if not SNAKE_CASE.match(topic.id):
            issues.append(f"topic id '{topic.id}' is not snake_case")
        for prerequisite in topic.prerequisites:
            if prerequisite == topic.id:
                issues.append(f"{topic.id}: a topic cannot be its own prerequisite")
            elif prerequisite not in known:
                issues.append(f"{topic.id}: prerequisite '{prerequisite}' does not exist")
        count = len(topic.learning_outcomes)
        if not MIN_OUTCOMES_PER_TOPIC <= count <= MAX_OUTCOMES_PER_TOPIC:
            issues.append(f"{topic.id}: {count} learning outcomes (expected 2 to 4)")
        for n, outcome in enumerate(topic.learning_outcomes, start=1):
            if outcome.id != f"lo_{topic.id}_{n}":
                issues.append(f"{topic.id}: outcome id '{outcome.id}' should be lo_{topic.id}_{n}")
            outcome_ids.append(outcome.id)
        if topic.learning_outcomes:
            top = max(bloom_rank(o.bloom_level) for o in topic.learning_outcomes)
            if bloom_rank(topic.bloom_level) != top:
                issues.append(f"{topic.id}: bloom_level is not the highest of its outcomes")
        if topic.estimated_hours < 0:
            issues.append(f"{topic.id}: estimated_hours cannot be negative")
    issues += [f"duplicated outcome id '{d}'" for d in _duplicates(outcome_ids)]
    cycle = find_cycle({t.id: t.prerequisites for t in syllabus.topics})
    if cycle:
        issues.append(f"prerequisite cycle: {' -> '.join(cycle)}")
    return issues


# ---------- Assessment items ----------


def check_assessment_items(items: AssessmentItemsLLM, outcomes: OutcomesByTopic) -> list[str]:
    """Existing topic and outcome, one correct index, 4 options, rubric that adds up to 1."""
    issues: list[str] = []
    if not items.items:
        return ["no items were generated"]
    issues += [f"duplicated item id '{d}'" for d in _duplicates([i.id for i in items.items])]
    for item in items.items:
        tag = item.id
        if item.topic_id not in outcomes:
            issues.append(f"{tag}: topic '{item.topic_id}' does not exist")
        elif item.outcome_id not in outcomes[item.topic_id]:
            issues.append(f"{tag}: outcome '{item.outcome_id}' is not of topic '{item.topic_id}'")
        if not 1 <= item.difficulty <= MAX_DIFFICULTY:
            issues.append(f"{tag}: difficulty {item.difficulty} out of 1..3")
        if not item.stem.strip():
            issues.append(f"{tag}: empty stem")
        if item.item_type == "multiple_choice":
            if len(item.options) != MULTIPLE_CHOICE_OPTIONS:
                issues.append(f"{tag}: {len(item.options)} options (expected 4)")
            elif len({o.strip().casefold() for o in item.options}) != MULTIPLE_CHOICE_OPTIONS:
                issues.append(f"{tag}: repeated options")
            if not 0 <= item.correct_option < max(1, len(item.options)):
                issues.append(f"{tag}: correct_option {item.correct_option} out of range")
            if item.rubric:
                issues.append(f"{tag}: multiple choice must have an empty rubric")
        else:
            if item.options:
                issues.append(f"{tag}: short answer must have no options")
            if item.correct_option != -1:
                issues.append(f"{tag}: short answer must have correct_option -1")
            issues += _rubric_issues(tag, [(c.criterion, c.points) for c in item.rubric])
    return issues


def _rubric_issues(tag: str, rubric: Sequence[tuple[str, float]]) -> list[str]:
    issues: list[str] = []
    if not RUBRIC_MIN_CRITERIA <= len(rubric) <= RUBRIC_MAX_CRITERIA:
        issues.append(f"{tag}: {len(rubric)} rubric criteria (expected 2 to 3)")
    if any(points <= 0 for _, points in rubric):
        issues.append(f"{tag}: rubric points must be positive")
    total = math.fsum(points for _, points in rubric)
    if rubric and abs(total - 1) > RUBRIC_POINTS_TOLERANCE:
        issues.append(f"{tag}: rubric points add up to {total} (expected 1)")
    if _duplicates([criterion for criterion, _ in rubric]):
        issues.append(f"{tag}: repeated rubric criteria")
    return issues


def check_diagnostic_coverage(items: AssessmentItemsLLM, topic_ids: Sequence[str]) -> list[str]:
    """Exactly 3 multiple-choice items per topic: remember/1, apply/2, analyze/3."""
    issues: list[str] = []
    for topic_id in topic_ids:
        found = sorted(
            ((i.bloom_level, i.difficulty) for i in items.items if i.topic_id == topic_id),
            key=lambda pair: pair[1],
        )
        if found != list(DIAGNOSTIC_PATTERN):
            issues.append(f"{topic_id}: diagnostic items {found} (expected {DIAGNOSTIC_PATTERN})")
    issues += [
        f"{i.id}: the diagnostic only uses multiple choice"
        for i in items.items
        if i.item_type != "multiple_choice"
    ]
    return issues


def check_final_coverage(
    items: AssessmentItemsLLM,
    path_topic_ids: Sequence[str],
    *,
    short_answers: int,
    versions: int,
) -> list[str]:
    """Final bank: per path topic at least 2 multiple-choice groups, ``short_answers``
    short-answer groups, and each ``equivalence_group`` with exactly ``versions`` parallel
    items (same topic, outcome, type, Bloom level and difficulty)."""
    issues: list[str] = []
    path = set(path_topic_ids)
    groups: dict[str, list[AssessmentItemLLM]] = {}
    for item in items.items:
        if item.topic_id not in path:
            issues.append(f"{item.id}: topic '{item.topic_id}' is not in the learning path")
        if not item.equivalence_group.strip():
            issues.append(f"{item.id}: final items need equivalence_group")
            continue
        groups.setdefault(item.equivalence_group, []).append(item)
    for group, members in groups.items():
        if len(members) != versions:
            issues.append(f"{group}: {len(members)} versions (expected {versions})")
        signatures = {
            (m.topic_id, m.outcome_id, m.item_type, m.bloom_level, m.difficulty) for m in members
        }
        if len(signatures) > 1:
            issues.append(f"{group}: parallel versions differ in topic, outcome, type or level")
    for topic_id in path_topic_ids:
        n = len(
            {
                g
                for g, members in groups.items()
                if members[0].topic_id == topic_id and members[0].item_type == "multiple_choice"
            }
        )
        if n < FINAL_MC_PER_TOPIC:
            issues.append(f"{topic_id}: {n} multiple-choice items (expected at least 2)")
    n_short = len({g for g, m in groups.items() if m[0].item_type == "short_answer"})
    if n_short < short_answers:
        issues.append(f"{n_short} short-answer items (expected {short_answers})")
    return issues


def check_item_reviews(reviews: ItemReviewLLM, item_ids: Sequence[str]) -> list[str]:
    """Every item reviewed exactly once and no review of an unknown item."""
    reviewed = [r.item_id for r in reviews.reviews]
    issues = [f"item '{d}' reviewed more than once" for d in _duplicates(reviewed)]
    issues += [f"review of unknown item '{i}'" for i in sorted(set(reviewed) - set(item_ids))]
    issues += [f"item '{i}' was not reviewed" for i in item_ids if i not in set(reviewed)]
    return issues


def discarded_item_ids(reviews: ItemReviewLLM) -> list[str]:
    """Items without a single correct answer (L-03): stored as ``auto_rejected``."""
    return [r.item_id for r in reviews.reviews if not r.single_correct_answer]


def check_simulated_answers(
    answers: SimulatedAnswersLLM, item_types: Mapping[str, ItemType], *, allow_dont_know: bool
) -> list[str]:
    """One answer per item; option index in range; «No lo sé» only in the diagnostic."""
    given = [a.item_id for a in answers.answers]
    issues = [f"item '{d}' answered more than once" for d in _duplicates(given)]
    issues += [f"answer to unknown item '{i}'" for i in sorted(set(given) - set(item_types))]
    issues += [f"item '{i}' was not answered" for i in item_types if i not in set(given)]
    for answer in answers.answers:
        kind = item_types.get(answer.item_id)
        if answer.dont_know:
            if not allow_dont_know:
                issues.append(f"{answer.item_id}: «No lo sé» is only allowed in the diagnostic")
            if answer.selected_option != -1 or answer.text_answer:
                issues.append(f"{answer.item_id}: «No lo sé» has selected_option -1 and no text")
        elif kind == "multiple_choice":
            if not 0 <= answer.selected_option < MULTIPLE_CHOICE_OPTIONS or answer.text_answer:
                issues.append(f"{answer.item_id}: multiple choice needs an option 0..3 and no text")
        elif kind == "short_answer" and (answer.selected_option != -1 or not answer.text_answer):
            issues.append(f"{answer.item_id}: short answer needs selected_option -1 and a text")
    return issues


# ---------- Objective ----------


def check_objective(objective: ObjectiveLLM, topic_ids: Collection[str]) -> list[str]:
    """Three non-empty parts and focus topics that exist."""
    issues = [
        f"objective {name} is empty"
        for name, value in (
            ("statement", objective.statement),
            ("bloom_verb", objective.bloom_verb),
            ("content", objective.content),
            ("criterion", objective.criterion),
        )
        if not value.strip()
    ]
    issues += [
        f"focus topic '{t}' does not exist" for t in objective.focus_topics if t not in topic_ids
    ]
    return issues


# ---------- Content ----------


def _explanation_text(explanation: TopicExplanationLLM) -> str:
    parts = [explanation.title, *(f"{s.heading}: {s.body}" for s in explanation.sections)]
    return "\n".join([*parts, explanation.worked_example, explanation.summary])


def check_explanation(
    explanation: TopicExplanationLLM, fragments: int, *, kind: str = "main"
) -> list[str]:
    """Citations [n] within 1..fragments, section count and two reflection questions."""
    issues: list[str] = []
    cited = cited_numbers(_explanation_text(explanation))
    if out := sorted(n for n in cited if not 1 <= n <= fragments):
        issues.append(f"citations out of range 1..{fragments}: {out}")
    if not cited:
        issues.append("the explanation cites no fragment")
    low, high = SECTION_RANGE.get(kind, SECTION_RANGE["main"])
    if not low <= len(explanation.sections) <= high:
        issues.append(f"{len(explanation.sections)} sections (expected {low} to {high})")
    if len(explanation.reflection_questions) != REFLECTION_QUESTIONS:
        issues.append(f"{len(explanation.reflection_questions)} reflection questions (expected 2)")
    return issues


def uncited_sections(explanation: TopicExplanationLLM) -> list[str]:
    """Headings of sections without any citation (reported, not rejected; as the notebook)."""
    return [s.heading for s in explanation.sections if not cited_numbers(s.body)]


def check_faithfulness(check: FaithfulnessCheckLLM, fragments: int) -> list[str]:
    """At most 15 claims and citations within 1..fragments."""
    issues: list[str] = []
    if len(check.claims) > MAX_CLAIMS:
        issues.append(f"{len(check.claims)} claims (at most {MAX_CLAIMS})")
    for n, claim in enumerate(check.claims, start=1):
        if out := sorted(c for c in claim.citations if not 1 <= c <= fragments):
            issues.append(f"claim {n}: citations out of range 1..{fragments}: {out}")
    return issues


def check_personalized_example(example: PersonalizedExampleLLM) -> list[str]:
    return [
        f"{name} is empty"
        for name, value in (("example", example.example), ("connection", example.connection))
        if not value.strip()
    ]


# ---------- Grading and badge ----------


def check_short_answer_grading(
    grading: ShortAnswerGradingLLM, rubric: Sequence[RubricCriterion]
) -> list[str]:
    """Each rubric criterion graded once, literally, with 0 <= points_awarded <= points."""
    points = {c.criterion: c.points for c in rubric}
    graded = [c.criterion for c in grading.criteria]
    issues = [f"criterion '{d}' graded more than once" for d in _duplicates(graded)]
    issues += [f"criterion '{c}' is not in the rubric" for c in graded if c not in points]
    issues += [f"criterion '{c}' was not graded" for c in points if c not in set(graded)]
    for result in grading.criteria:
        maximum = points.get(result.criterion)
        if maximum is None:
            continue
        if not -POINTS_TOLERANCE <= result.points_awarded <= maximum + POINTS_TOLERANCE:
            issues.append(
                f"'{result.criterion}': points_awarded {result.points_awarded} out of 0..{maximum}"
            )
    if not grading.feedback.strip():
        issues.append("feedback is empty")
    return issues


def check_badge_text(badge: BadgeTextLLM) -> list[str]:
    issues = [
        f"{name} is empty"
        for name, value in (
            ("name", badge.name),
            ("description", badge.description),
            ("criteria", badge.criteria),
        )
        if not value.strip()
    ]
    if not MIN_COMPETENCIES <= len(badge.competencies) <= MAX_COMPETENCIES:
        issues.append(f"{len(badge.competencies)} competencies (expected 3 to 5)")
    return issues
