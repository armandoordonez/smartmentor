"""Base de los modelos SQLAlchemy. Reflejan el esquema que crea Liquibase; no lo definen."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TableModel(Base):
    """Columnas comunes de toda tabla de negocio.

    id, active y created_at tienen valor por defecto en la base de datos (secuencia propia
    <tabla>_id_seq); eager_defaults los trae de vuelta al insertar.
    """

    __abstract__ = True
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
