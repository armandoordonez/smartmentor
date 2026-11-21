"""``PromptStore`` port (plan 5.4.5): versioned prompts of ``prompts/`` and their schemas."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

ModelTier = Literal["default", "small"]

_DELIMITERS = re.compile(r"<<<|>>>")


def sanitize_data(value: str) -> str:
    """Remove ``<<<`` and ``>>>`` so user data cannot close its block (prompts/README, rule 2)."""
    return _DELIMITERS.sub("", value)


@dataclass(frozen=True)
class PromptTemplate:
    """One version of a prompt, parsed from ``prompts/<id>/v<n>.md``."""

    id: str
    version: int
    name_es: str
    task: str
    temperature: float
    model_tier: ModelTier
    output_schema_name: str  # e.g. "llm/syllabus_llm.v1.json"
    output_schema: dict[str, Any] = field(repr=False)
    contract: str
    data_variables: tuple[str, ...]
    parameter_variables: tuple[str, ...]
    system: str = field(repr=False)
    user: str = field(repr=False)
    sha256: str

    @property
    def version_label(self) -> str:
        """Version as stored in ``Meta.prompt_version`` and ``llm_call_logs`` (``v1``)."""
        return f"v{self.version}"

    def render(self, variables: Mapping[str, Any]) -> str:
        """Fill ``{name}`` placeholders; data variables are sanitised first."""
        expected = set(self.data_variables) | set(self.parameter_variables)
        if missing := sorted(expected - set(variables)):
            raise KeyError(f"{self.id}: missing prompt variables {missing}")
        values = {
            name: sanitize_data(str(value)) if name in self.data_variables else value
            for name, value in variables.items()
        }
        return self.user.format(**values)


@dataclass(frozen=True)
class PromptCatalogEntry:
    """A ``catalog.yaml`` entry (``GET /v1/prompts``)."""

    id: str
    name_es: str
    task: str
    current_version: int
    model_tier: ModelTier
    temperature: float
    output_schema: str
    contract: str
    screens: tuple[str, ...]
    versions: Mapping[int, str]


class PromptNotFoundError(KeyError):
    pass


class PromptStore(Protocol):
    def get(self, prompt_id: str, version: int | None = None) -> PromptTemplate:
        """Current version when ``version`` is ``None``. Raises ``PromptNotFoundError``."""
        ...

    def catalog(self) -> list[PromptCatalogEntry]: ...

    def verify(self) -> list[str]:
        """Problems found (hash mismatch, missing file or schema); empty = ready."""
        ...
