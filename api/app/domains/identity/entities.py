"""Entidades del dominio de identidad (Python puro)."""

from dataclasses import dataclass

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


@dataclass(kw_only=True)
class UserRole(BaseEntity):
    user_id: int
    role_id: int
