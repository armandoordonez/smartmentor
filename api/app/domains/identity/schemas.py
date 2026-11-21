"""Contratos HTTP de identidad (docs/contracts/api-v2.md, secciones 2 y 6)."""

from typing import Self

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.common.constants import (
    ConsentType,
    DataSubjectRequestType,
    EducationLevel,
    ExperienceBand,
    RoleCode,
)
from app.common.schemas import RequestSchema, ResponseSchema, UtcDatetime


class RoleCreate(RequestSchema):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class RoleUpdate(RequestSchema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class RoleResponse(ResponseSchema):
    code: str
    name: str
    description: str | None


def _check_identity_pair(provider: str | None, subject: str | None) -> None:
    if (provider is None) != (subject is None):
        raise ValueError("identity_provider and identity_subject must be set together")


class UserCreate(RequestSchema):
    full_name: str = Field(min_length=1, max_length=200)
    email: EmailStr = Field(max_length=320)
    identity_provider: str | None = Field(default=None, max_length=50)
    identity_subject: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def identity_fields_go_together(self) -> Self:
        _check_identity_pair(self.identity_provider, self.identity_subject)
        return self


class UserUpdate(RequestSchema):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = Field(default=None, max_length=320)
    identity_provider: str | None = Field(default=None, max_length=50)
    identity_subject: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def identity_fields_go_together(self) -> Self:
        sent = self.model_fields_set
        if ("identity_provider" in sent) != ("identity_subject" in sent):
            raise ValueError("identity_provider and identity_subject must be sent together")
        if "identity_provider" in sent:
            _check_identity_pair(self.identity_provider, self.identity_subject)
        if "full_name" in sent and self.full_name is None:
            raise ValueError("full_name cannot be null")
        if "email" in sent and self.email is None:
            raise ValueError("email cannot be null")
        return self


class UserResponse(ResponseSchema):
    full_name: str
    email: str
    identity_provider: str | None
    identity_subject: str | None


class UserRoleCreate(RequestSchema):
    user_id: int = Field(gt=0)
    role_id: int = Field(gt=0)


class UserRoleUpdate(RequestSchema):
    """Una asignación de rol no tiene campos editables: se activa o se inactiva."""


class UserRoleResponse(ResponseSchema):
    user_id: int
    role_id: int


class UserRolesUpdate(RequestSchema):
    """`PUT /users/{id}/roles`: el conjunto completo de roles del usuario (al menos uno)."""

    roles: list[RoleCode] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def no_duplicates(self) -> Self:
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("roles must not repeat")
        return self


class UserRolesResponse(BaseModel):
    roles: list[str]


# --- GET /me ---------------------------------------------------------------------------------


class ConsentState(BaseModel):
    granted: bool
    document_version: str | None
    granted_at: UtcDatetime | None


class ProfileCompletenessResponse(BaseModel):
    description: bool
    resume: bool
    percent: int


class MeResponse(BaseModel):
    """El usuario autenticado y sus roles (CU-34, CU-35)."""

    id: int
    email: str
    full_name: str
    roles: list[str]
    role_labels: dict[str, str]
    role_short_labels: dict[str, str]
    default_role: str | None
    is_new_user: bool
    consent_status: dict[str, ConsentState]
    requires_consent: bool
    profile_completeness: ProfileCompletenessResponse
    second_factor: bool


# --- Perfil, autorizaciones y solicitudes -----------------------------------------------------


class LanguageSkill(RequestSchema):
    code: str = Field(min_length=2, max_length=10)
    cefr_level: str = Field(pattern=r"^(A1|A2|B1|B2|C1|C2)$")


class ProfileUpdate(RequestSchema):
    description: str | None = Field(default=None, max_length=4000)
    education_level: EducationLevel | None = None
    qualification_title: str | None = Field(default=None, max_length=200)
    job_title: str | None = Field(default=None, max_length=200)
    experience_band: ExperienceBand | None = None
    tools: list[str] = Field(default_factory=list, max_length=50)
    languages: list[LanguageSkill] = Field(default_factory=list, max_length=20)


class ProfileResponse(BaseModel):
    description: str | None
    education_level: str | None
    qualification_title: str | None
    job_title: str | None
    experience_band: str | None
    tools: list[str]
    languages: list[LanguageSkill]
    resume_completed_at: UtcDatetime | None
    recalculated_enrollment_ids: list[int] | None = None


class ConsentCreate(RequestSchema):
    consent_type: ConsentType
    document_version: str = Field(min_length=1, max_length=30)


class ConsentResponse(BaseModel):
    id: int
    consent_type: str
    document_version: str
    granted_at: UtcDatetime | None
    revoked_at: UtcDatetime | None
    granted: bool


class DataSubjectRequestCreate(RequestSchema):
    request_type: DataSubjectRequestType
    comment: str | None = Field(default=None, max_length=2000)


class DataSubjectRequestResponse(BaseModel):
    id: int
    request_type: str
    status: str
