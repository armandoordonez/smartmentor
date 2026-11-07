"""Entidades del dominio de identidad (Python puro)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.common.entities import BaseEntity


@dataclass(kw_only=True)
class Role(BaseEntity):
    code: str
    name: str
    description: str | None = None


@dataclass(kw_only=True)
class User(BaseEntity):
    full_name: str
    email: str
    identity_provider: str | None = None
    identity_subject: str | None = None
    updated_at: datetime | None = None


@dataclass(kw_only=True)
class UserRole(BaseEntity):
    user_id: int
    role_id: int


@dataclass(kw_only=True)
class UserProfile(BaseEntity):
    user_id: int
    description: str | None = None
    education_level: str | None = None
    qualification_title: str | None = None
    job_title: str | None = None
    experience_band: str | None = None
    tools: list[Any] = field(default_factory=list)
    languages: list[Any] = field(default_factory=list)
    resume_completed_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def has_description(self) -> bool:
        return bool(self.description and self.description.strip())

    @property
    def has_resume(self) -> bool:
        return self.resume_completed_at is not None


@dataclass(kw_only=True)
class Consent(BaseEntity):
    user_id: int
    consent_type: str
    document_version: str
    granted_at: datetime | None = None
    revoked_at: datetime | None = None

    @property
    def in_force(self) -> bool:
        return self.active and self.revoked_at is None


@dataclass(kw_only=True)
class DataSubjectRequest(BaseEntity):
    user_id: int
    request_type: str
    status: str = "pending"
    details: str | None = None
    resolved_at: datetime | None = None
    resolved_by_user_id: int | None = None
    updated_at: datetime | None = None
