"""Shared types for the AI contracts.

Two layers per AI output (as in the Wizard of Oz notebook v2):

* ``...LLM`` models: what the provider must return. They are flat (no unions, no free-form
  dictionaries, no numeric ranges) because structured-output providers honour those worse.
  Ranges and cross-references are checked in code (``validation.py``).
* Contract models: what ``ai/`` hands to the API. Strict (``extra="forbid"``), with ranges and
  intrinsic invariants enforced by Pydantic validators.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BloomLevel = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]
BLOOM_ORDER: tuple[BloomLevel, ...] = (
    "remember",
    "understand",
    "apply",
    "analyze",
    "evaluate",
    "create",
)

ItemType = Literal["multiple_choice", "short_answer"]
ItemSource = Literal["diagnostic", "topic_quiz", "final", "retention"]

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
CITATION = re.compile(r"\[(\d+)\]")
MULTIPLE_CHOICE_OPTIONS = 4


class LlmModel(BaseModel):
    """Base for the schemas sent to the LLM provider (lenient with unknown keys)."""

    model_config = ConfigDict(extra="ignore")


class ContractModel(BaseModel):
    """Base for the contracts that ``ai/`` returns to the API (strict)."""

    model_config = ConfigDict(extra="forbid")


class Meta(ContractModel):
    """Traceability of an LLM-generated output."""

    prompt_id: str = Field(description="Prompt id from prompts/catalog.yaml, e.g. topic_quiz")
    prompt_version: str = Field(pattern=r"^v\d+$", description="Prompt file version, e.g. v1")
    model: str = Field(description="Provider model name used for the call")
    generated_at: datetime
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="Cache key (SHA-256)")
    from_cache: bool = False


def bloom_rank(level: BloomLevel) -> int:
    """Position of a Bloom level (0 = remember, 5 = create)."""
    return BLOOM_ORDER.index(level)


def cited_numbers(text: str) -> set[int]:
    """Citation numbers ``[n]`` that appear in a text."""
    return {int(match) for match in CITATION.findall(text)}
