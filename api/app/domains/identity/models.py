"""Modelos SQLAlchemy de identidad. Reflejan las tablas del esquema v2.0.0 (Liquibase)."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TableModel, UpdatableTableModel


class RoleModel(TableModel):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)


class UserModel(UpdatableTableModel):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    identity_provider: Mapped[str | None] = mapped_column(String(50))
    identity_subject: Mapped[str | None] = mapped_column(String(255))


class UserRoleModel(TableModel):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("roles.id"))


class UserProfileModel(UpdatableTableModel):
    """Descripción y hoja de vida (1 a 1 con users). `tools` y `languages` son jsonb."""

    __tablename__ = "user_profiles"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    description: Mapped[str | None] = mapped_column(Text)
    education_level: Mapped[str | None] = mapped_column(String(20))
    qualification_title: Mapped[str | None] = mapped_column(String(200))
    job_title: Mapped[str | None] = mapped_column(String(200))
    experience_band: Mapped[str | None] = mapped_column(String(30))
    tools: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    languages: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    resume_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConsentModel(TableModel):
    __tablename__ = "consents"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    consent_type: Mapped[str] = mapped_column(String(30))
    document_version: Mapped[str] = mapped_column(String(30))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DataSubjectRequestModel(UpdatableTableModel):
    __tablename__ = "data_subject_requests"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    request_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    comment: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
