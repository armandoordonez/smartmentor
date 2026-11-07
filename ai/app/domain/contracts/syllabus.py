"""Syllabus structuring: ``syllabus_structuring`` prompt -> ``syllabus.v1`` contract."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from app.domain.contracts.common import (
    SNAKE_CASE,
    BloomLevel,
    ContractModel,
    LlmModel,
    Meta,
    bloom_rank,
)
from app.domain.contracts.graph import find_cycle

# ---------- LLM output ----------


class LearningOutcomeLLM(LlmModel):
    id: str = Field(description="lo_<topic id>_<n>")
    statement: str = Field(description="Bloom verb + content + measurable criterion (Spanish)")
    bloom_level: BloomLevel


class SyllabusTopicLLM(LlmModel):
    id: str = Field(description="Short, stable snake_case id, e.g. regresion_logistica")
    name: str
    description: str
    subtopics: list[str]
    learning_outcomes: list[LearningOutcomeLLM]
    bloom_level: BloomLevel = Field(description="Highest Bloom level among its outcomes")
    prerequisites: list[str] = Field(description="Topic ids of this same syllabus")
    estimated_hours: int = Field(description="Hours stated by the syllabus; 0 when not stated")


class SyllabusLLM(LlmModel):
    course_key: str = Field(description="snake_case key of the course")
    course_name: str
    default_objective: str = Field(description="General course objective as a measurable outcome")
    topics: list[SyllabusTopicLLM]


# ---------- Contract ----------


class LearningOutcome(ContractModel):
    id: str = Field(pattern=r"^lo_[a-z0-9_]+_\d+$")
    statement: str = Field(min_length=1)
    bloom_level: BloomLevel


class SyllabusTopic(ContractModel):
    id: str = Field(
        pattern=SNAKE_CASE.pattern,
        description="Extraction key (stored in topics.extraction_key)",
    )
    name: str = Field(min_length=1)
    description: str
    subtopics: list[str]
    learning_outcomes: list[LearningOutcome] = Field(min_length=1)
    bloom_level: BloomLevel
    prerequisites: list[str]
    estimated_minutes: int | None = Field(
        default=None, ge=1, description="Null when the syllabus does not state it (L-05)"
    )
    is_mandatory: bool = False


class Syllabus(ContractModel):
    course_key: str = Field(pattern=SNAKE_CASE.pattern)
    course_name: str = Field(min_length=1)
    default_objective: str
    topics: list[SyllabusTopic] = Field(min_length=1)
    meta: Meta

    @model_validator(mode="after")
    def _check_graph(self) -> Self:
        ids = [t.id for t in self.topics]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicated topic ids: {ids}")
        known = set(ids)
        outcome_ids: list[str] = []
        for topic in self.topics:
            missing = [p for p in topic.prerequisites if p not in known]
            if missing:
                raise ValueError(f"{topic.id}: unknown prerequisites {missing}")
            if topic.id in topic.prerequisites:
                raise ValueError(f"{topic.id}: a topic cannot be its own prerequisite")
            top = max(bloom_rank(o.bloom_level) for o in topic.learning_outcomes)
            if bloom_rank(topic.bloom_level) != top:
                raise ValueError(f"{topic.id}: bloom_level must be the highest of its outcomes")
            outcome_ids += [o.id for o in topic.learning_outcomes]
        if len(outcome_ids) != len(set(outcome_ids)):
            raise ValueError("duplicated learning outcome ids")
        cycle = find_cycle({t.id: t.prerequisites for t in self.topics})
        if cycle:
            raise ValueError(f"prerequisite cycle: {' -> '.join(cycle)}")
        return self


def syllabus_from_llm(llm: SyllabusLLM, meta: Meta) -> Syllabus:
    """Build the contract from a checked LLM output (hours -> minutes, 0 -> null)."""
    return Syllabus(
        course_key=llm.course_key,
        course_name=llm.course_name,
        default_objective=llm.default_objective,
        meta=meta,
        topics=[
            SyllabusTopic(
                id=t.id,
                name=t.name,
                description=t.description,
                subtopics=t.subtopics,
                learning_outcomes=[
                    LearningOutcome.model_validate(o.model_dump()) for o in t.learning_outcomes
                ],
                bloom_level=t.bloom_level,
                prerequisites=t.prerequisites,
                estimated_minutes=t.estimated_hours * 60 if t.estimated_hours > 0 else None,
            )
            for t in llm.topics
        ],
    )
