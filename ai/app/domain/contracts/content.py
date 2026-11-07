"""Topic content: explanation (main and remedial), faithfulness check and personalised example.

Prompts: ``topic_explanation`` and ``remedial_explanation`` -> ``topic_explanation.v1``;
``rag_faithfulness`` -> ``faithfulness_check.v1``; ``personalized_example`` ->
``personalized_example.v1``.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel, LlmModel, Meta, cited_numbers

MAX_CLAIMS = 15
FAITHFULNESS_TOLERANCE = 0.001

# ---------- LLM output ----------


class SectionLLM(LlmModel):
    heading: str
    body: str = Field(description="Text with [n] citations to the fragments")


class TopicExplanationLLM(LlmModel):
    title: str
    sections: list[SectionLLM]
    worked_example: str
    summary: str
    reflection_questions: list[str]
    gaps_detected: list[str] = Field(description="Learning outcomes the fragments do not cover")


class ClaimLLM(LlmModel):
    text: str
    citations: list[int]
    supported: bool
    comment: str


class FaithfulnessCheckLLM(LlmModel):
    claims: list[ClaimLLM]


class PersonalizedExampleLLM(LlmModel):
    example: str
    connection: str


# ---------- Contracts ----------


class Section(ContractModel):
    heading: str = Field(min_length=1)
    body: str = Field(min_length=1)


class CitedSource(ContractModel):
    n: int = Field(ge=1, description="Citation number used as [n] in the text")
    source_id: str = Field(description="Key of the fragment (document_chunks)")
    title: str
    url: str
    license: str | None = None


class TopicExplanation(ContractModel):
    topic_id: str
    kind: Literal["main", "remedial"]
    audience: Literal["all_learners", "enrollment"] = Field(
        description="main = shared by every learner (L-01); remedial = personal"
    )
    version: str = Field(default="1.0", pattern=r"^\d+\.\d+$", description="Shown in D5d")
    edited_by_user_id: int | None = Field(default=None, description="Set by the API on edits")
    title: str = Field(min_length=1)
    sections: list[Section] = Field(min_length=1)
    worked_example: str
    summary: str
    reflection_questions: list[str]
    gaps_detected: list[str]
    sources: list[CitedSource] = Field(min_length=1)
    faithfulness: float | None = Field(default=None, ge=0, le=1)
    unsupported_claims: list[str] = Field(default_factory=list)
    meta: Meta

    def full_text(self) -> str:
        parts = [self.title, *(f"{s.heading}: {s.body}" for s in self.sections)]
        return "\n".join([*parts, self.worked_example, self.summary])

    @model_validator(mode="after")
    def _check_citations(self) -> Self:
        expected_audience = "all_learners" if self.kind == "main" else "enrollment"
        if self.audience != expected_audience:
            raise ValueError(f"a {self.kind} explanation has audience {expected_audience}")
        numbers = [s.n for s in self.sources]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("sources must be numbered 1..k in order")
        if out_of_range := sorted(n for n in cited_numbers(self.full_text()) if n > len(numbers)):
            raise ValueError(f"citations out of range 1..{len(numbers)}: {out_of_range}")
        if 0 in cited_numbers(self.full_text()):
            raise ValueError("citation [0] is not valid")
        return self


class Claim(ContractModel):
    text: str = Field(min_length=1)
    citations: list[int]
    supported: bool
    comment: str


class FaithfulnessCheck(ContractModel):
    """Result of ``content.check_faithfulness``."""

    claims: list[Claim] = Field(max_length=MAX_CLAIMS)
    faithfulness: float = Field(ge=0, le=1, description="Supported claims / total claims")
    unsupported_claims: list[str]
    meta: Meta

    @model_validator(mode="after")
    def _check_ratio(self) -> Self:
        supported = sum(c.supported for c in self.claims)
        expected = supported / len(self.claims) if self.claims else 1.0
        if abs(self.faithfulness - expected) > FAITHFULNESS_TOLERANCE:
            raise ValueError(f"faithfulness must be {expected:.3f}")
        if self.unsupported_claims != [c.text for c in self.claims if not c.supported]:
            raise ValueError("unsupported_claims must list the unsupported claims in order")
        return self


class PersonalizedExample(ContractModel):
    topic_id: str
    example: str = Field(min_length=1)
    connection: str = Field(min_length=1)
    meta: Meta


def faithfulness_from_llm(check: FaithfulnessCheckLLM, meta: Meta) -> FaithfulnessCheck:
    """Contract from a checked LLM output (ratio rounded to 3 decimals, as the notebook)."""
    claims = [Claim.model_validate(c.model_dump()) for c in check.claims]
    supported = sum(c.supported for c in claims)
    return FaithfulnessCheck(
        claims=claims,
        faithfulness=round(supported / len(claims), 3) if claims else 1.0,
        unsupported_claims=[c.text for c in claims if not c.supported],
        meta=meta,
    )
