"""``badge.compose_text``: the text of the badge (``ai/`` only writes the text; the API builds the
Open Badges assertion with a hashed, salted recipient)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.application.content.context import TaskContext, TaskResult, to_json
from app.application.llm_runner import LlmRunner
from app.domain.contracts.badge import BadgeText, BadgeTextLLM
from app.domain.contracts.validation import check_badge_text

BADGE_CONTRACT = "badge_text.v1"


class BadgeTextInput(BaseModel):
    course_name: str = Field(min_length=1)
    objective_statement: str = ""
    topic_names: list[str] = Field(min_length=1)
    final_pass_threshold: int = Field(ge=0, le=100)


class BadgeTextTask:
    job_type = "badge.compose_text"

    def __init__(self, runner: LlmRunner) -> None:
        self._runner = runner

    async def run(self, raw: dict[str, Any], ctx: TaskContext) -> TaskResult:
        data = BadgeTextInput.model_validate(raw)
        llm, meta = await self._runner.run(
            "badge_text",
            {
                "course": data.course_name,
                "objective": data.objective_statement,
                "topics": to_json(data.topic_names),
                "threshold": data.final_pass_threshold,
            },
            BadgeTextLLM,
            ctx.call(self.job_type),
            check=check_badge_text,
        )
        badge = BadgeText(
            name=llm.name,
            description=llm.description,
            criteria=llm.criteria,
            competencies=llm.competencies,
            meta=meta,
        )
        return TaskResult(BADGE_CONTRACT, badge.model_dump(mode="json"))
