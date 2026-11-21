"""``content.personal_example``: a short example that connects the topic with the learner (P2).

The profile is pseudonymised before it is sent, and the answer is never cached (it is personal).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.application.content.context import (
    TaskContext,
    TaskResult,
    load_topic,
    to_json,
    topic_payload,
)
from app.application.content.privacy import pseudonymize_profile
from app.application.llm_runner import LlmRunner
from app.domain.contracts.content import PersonalizedExample, PersonalizedExampleLLM
from app.domain.contracts.validation import check_personalized_example
from app.ports.catalog import CatalogReader

PERSONAL_EXAMPLE_CONTRACT = "personalized_example.v1"


class PersonalExampleInput(BaseModel):
    topic_id: str
    profile_text: str = ""


class PersonalExampleTask:
    job_type = "content.personal_example"

    def __init__(self, *, runner: LlmRunner, catalog: CatalogReader) -> None:
        self._runner = runner
        self._catalog = catalog

    async def run(self, raw: dict[str, Any], ctx: TaskContext) -> TaskResult:
        data = PersonalExampleInput.model_validate(raw)
        topic = await load_topic(self._catalog, data.topic_id)
        llm, meta = await self._runner.run(
            "personalized_example",
            {
                "topic": to_json(topic_payload(topic)),
                "profile": pseudonymize_profile(data.profile_text),
            },
            PersonalizedExampleLLM,
            ctx.call(self.job_type, course_id=topic.course_id),
            check=check_personalized_example,
            use_cache=False,
        )
        example = PersonalizedExample(
            topic_id=topic.id, example=llm.example, connection=llm.connection, meta=meta
        )
        return TaskResult(PERSONAL_EXAMPLE_CONTRACT, example.model_dump(mode="json"))
