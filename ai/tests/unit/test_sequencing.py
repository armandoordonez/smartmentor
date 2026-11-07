"""``app/domain/sequencing.py``: contract example and properties over random DAGs."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.contracts.learning_path import PilotArm
from app.domain.sequencing import PathTopic, SequencingError, sequence_path

EXAMPLE = [
    PathTopic("10", 1, []),
    PathTopic("11", 2, ["10"]),
    PathTopic("12", 3, ["10", "11"]),
]
LEVELS = {"10": 95.5, "11": 64.4, "12": 4.4}


def test_contract_example() -> None:
    path = sequence_path(EXAMPLE, LEVELS, mastery_skip_threshold=80, focus_topic_ids=["12"])
    assert [(s.topic_id, s.status, s.inclusion_reason) for s in path.steps] == [
        ("10", "skipped", "skipped_mastered"),
        ("11", "pending", "weak_prerequisite"),
        ("12", "blocked", "objective_focus"),
    ]


def test_fixed_arm_includes_everything() -> None:
    path = sequence_path(EXAMPLE, LEVELS, mastery_skip_threshold=80, pilot_arm="fixed")
    assert {s.inclusion_reason for s in path.steps} == {"fixed_path"}
    assert [s.status for s in path.steps] == ["pending", "blocked", "blocked"]


def test_mandatory_topic_is_never_skipped() -> None:
    topics = [PathTopic("10", 1, [], is_mandatory=True), *EXAMPLE[1:]]
    path = sequence_path(topics, LEVELS, mastery_skip_threshold=80)
    assert path.steps[0].status == "pending"
    assert path.steps[0].inclusion_reason == "mandatory"


def test_position_order_is_kept_when_the_graph_allows_it() -> None:
    topics = [PathTopic("b", 2), PathTopic("a", 1), PathTopic("c", 3, ["b"])]
    path = sequence_path(topics, {}, mastery_skip_threshold=80)
    assert [s.topic_id for s in path.steps] == ["a", "b", "c"]
    assert [s.status for s in path.steps] == ["pending", "pending", "blocked"]


def test_invalid_graphs() -> None:
    with pytest.raises(SequencingError) as self_loop:
        sequence_path([PathTopic("a", 1, ["a"])], {}, mastery_skip_threshold=80)
    assert self_loop.value.code == "PREREQUISITE_SELF"
    with pytest.raises(SequencingError) as cycle:
        sequence_path(
            [PathTopic("a", 1, ["b"]), PathTopic("b", 2, ["a"])], {}, mastery_skip_threshold=80
        )
    assert cycle.value.code == "VALIDATION_ERROR"
    assert cycle.value.cycle is not None
    with pytest.raises(SequencingError):
        sequence_path([PathTopic("a", 1, ["zz"])], {}, mastery_skip_threshold=80)


@st.composite
def dags(draw: st.DrawFn) -> tuple[list[PathTopic], dict[str, float], float, list[str]]:
    n = draw(st.integers(1, 12))
    ids = [f"t{i}" for i in range(n)]
    # Edges only from earlier to later ids in a random permutation: always acyclic.
    order = draw(st.permutations(ids))
    topics = []
    for index, topic_id in enumerate(order):
        prereqs = draw(st.lists(st.sampled_from(order[:index]), unique=True)) if index else []
        topics.append(
            PathTopic(
                topic_id,
                position=draw(st.integers(0, 20)),
                prerequisites=prereqs,
                is_mandatory=draw(st.booleans()),
            )
        )
    levels = {t: draw(st.floats(0, 100)) for t in ids if draw(st.booleans())}
    threshold = draw(st.floats(0, 100))
    focus = draw(st.lists(st.sampled_from(ids), unique=True))
    return draw(st.permutations(topics)), levels, threshold, focus


@settings(max_examples=300, deadline=None)
@given(case=dags(), arm=st.sampled_from(["personalized", "fixed"]))
def test_properties_on_random_dags(
    case: tuple[list[PathTopic], dict[str, float], float, list[str]], arm: str
) -> None:
    topics, levels, threshold, focus = case
    pilot_arm: PilotArm = "fixed" if arm == "fixed" else "personalized"
    path = sequence_path(
        topics, levels, mastery_skip_threshold=threshold, focus_topic_ids=focus, pilot_arm=pilot_arm
    )
    by_id = {t.topic_id: t for t in topics}
    steps = path.steps
    position = {s.topic_id: s.step_order for s in steps}
    # Every topic exactly once (the contract validator also checks it).
    assert sorted(position) == sorted(by_id)
    # Prerequisites come first.
    for topic in topics:
        assert all(position[p] < position[topic.topic_id] for p in topic.prerequisites)
    skipped = {s.topic_id for s in steps if s.status == "skipped"}
    for step in steps:
        topic = by_id[step.topic_id]
        should_skip = (
            pilot_arm != "fixed"
            and not topic.is_mandatory
            and step.topic_id in levels
            and levels[step.topic_id] >= threshold
        )
        assert (step.topic_id in skipped) == should_skip
        if step.status != "skipped":
            waiting = any(p not in skipped for p in topic.prerequisites)
            assert step.status == ("blocked" if waiting else "pending")
    # The first included step is always available.
    included = [s for s in steps if s.status != "skipped"]
    if included:
        assert included[0].status == "pending"
    # Deterministic.
    again = sequence_path(
        topics, levels, mastery_skip_threshold=threshold, focus_topic_ids=focus, pilot_arm=pilot_arm
    )
    assert again == path
