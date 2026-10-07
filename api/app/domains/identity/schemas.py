"""Contratos HTTP de identidad."""

from typing import Self

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.common.schemas import RequestSchema, ResponseSchema


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


class MeResponse(BaseModel):
    """El usuario autenticado y sus roles. Se arma desde el token y la base de datos."""

    id: int
    full_name: str
    email: str
    roles: list[str]
    identity_provider: str | None
    identity_subject: str | None
