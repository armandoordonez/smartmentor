"""``path.sequence`` (synchronous, no LLM): input model and adapter to the domain."""

from __future__ import annotations

from pydantic import Field

from app.domain.contracts.common import ContractModel
from app.domain.contracts.learning_path import LearningPath, PilotArm
from app.domain.sequencing import PathTopic, sequence_path


class PathTopicInput(ContractModel):
    topic_id: str = Field(min_length=1)
    position: int = Field(ge=0)
    prerequisites: list[str] = Field(default_factory=list)
    is_mandatory: bool = False


class TopicLevelInput(ContractModel):
    topic_id: str = Field(min_length=1)
    level: float = Field(ge=0, le=100)


class PathSequenceInput(ContractModel):
    topics: list[PathTopicInput] = Field(min_length=1, max_length=200)
    level_by_topic: list[TopicLevelInput] = Field(default_factory=list)
    mastery_skip_threshold: float = Field(ge=0, le=100)
    focus_topic_ids: list[str] = Field(default_factory=list)
    pilot_arm: PilotArm | None = "personalized"


def sequence(payload: PathSequenceInput) -> LearningPath:
    """Raises ``SequencingError`` on an invalid graph."""
    return sequence_path(
        [
            PathTopic(
                topic_id=t.topic_id,
                position=t.position,
                prerequisites=t.prerequisites,
                is_mandatory=t.is_mandatory,
            )
            for t in payload.topics
        ],
        {lv.topic_id: lv.level for lv in payload.level_by_topic},
        mastery_skip_threshold=payload.mastery_skip_threshold,
        focus_topic_ids=payload.focus_topic_ids,
        pilot_arm=payload.pilot_arm,
    )
