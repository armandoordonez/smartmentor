"""Badge: ``badge_text`` prompt -> ``badge_text.v1``; Open Badges 2.0 assertion -> ``badge.v1``.

``ai/`` only writes the text (``badge.compose_text``). The API builds and serves the
assertion (``GET /api/v1/badges/{public_id}/assertion.json``) with a hashed, salted recipient.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from app.domain.contracts.common import ContractModel, LlmModel, Meta

MIN_COMPETENCIES = 3
MAX_COMPETENCIES = 5

# ---------- LLM output ----------


class BadgeTextLLM(LlmModel):
    name: str
    description: str
    criteria: str
    competencies: list[str]


# ---------- Contracts ----------


class BadgeText(ContractModel):
    """Result of ``badge.compose_text``."""

    name: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1)
    criteria: str = Field(min_length=1)
    competencies: list[str] = Field(min_length=MIN_COMPETENCIES, max_length=MAX_COMPETENCIES)
    meta: Meta


class _OpenBadgeModel(ContractModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ObCriteria(_OpenBadgeModel):
    narrative: str


class ObIssuer(_OpenBadgeModel):
    type: Literal["Profile"] = "Profile"
    id: str
    name: str
    url: str


class ObBadgeClass(_OpenBadgeModel):
    type: Literal["BadgeClass"] = "BadgeClass"
    id: str
    name: str
    description: str
    image: str
    criteria: ObCriteria
    issuer: ObIssuer
    tags: list[str]


class ObRecipient(_OpenBadgeModel):
    type: Literal["email"] = "email"
    hashed: Literal[True] = True
    salt: str = Field(min_length=8)
    identity: str = Field(pattern=r"^sha256\$[0-9a-f]{64}$", description="sha256(email + salt)")


class ObVerification(_OpenBadgeModel):
    type: Literal["hosted"] = "hosted"


class ObEvidence(_OpenBadgeModel):
    narrative: str


class BadgeAssertion(_OpenBadgeModel):
    """Open Badges 2.0 hosted assertion (E10, E12)."""

    context: Literal["https://w3id.org/openbadges/v2"] = Field(
        default="https://w3id.org/openbadges/v2", alias="@context"
    )
    type: Literal["Assertion"] = "Assertion"
    id: str = Field(description="Public URL of the assertion (uses the badge public_id)")
    recipient: ObRecipient
    badge: ObBadgeClass
    issued_on: datetime = Field(alias="issuedOn")
    verification: ObVerification = Field(default_factory=ObVerification)
    evidence: list[ObEvidence]
