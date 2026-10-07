"""Modelos SQLAlchemy de identidad. Reflejan las tablas roles, users y user_roles de Liquibase."""

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import TableModel


class RoleModel(TableModel):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)


class UserModel(TableModel):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    identity_provider: Mapped[str | None] = mapped_column(String(50))
    identity_subject: Mapped[str | None] = mapped_column(String(255))


class UserRoleModel(TableModel):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("roles.id"))
