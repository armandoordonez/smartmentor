"""Base de los modelos SQLAlchemy. Reflejan el esquema que crea Liquibase; no lo definen."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Uuid, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TableModel(Base):
    """Columnas comunes de toda tabla de negocio.

    id, active y created_at tienen valor por defecto en la base de datos (secuencia propia
    <tabla>_id_seq); eager_defaults los trae de vuelta al insertar.
    """

    __abstract__ = True
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012  (patrón documentado de SQLAlchemy)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UpdatableTableModel(TableModel):
    """Tabla de negocio que cambia: agrega `updated_at` (convención v2.0.0, sección 5.2.1)."""

    __abstract__ = True

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PublicTableModel(UpdatableTableModel):
    """Tabla que la API puede exponer: además del `id`, lleva un `public_id` uuid (sección 18.2)."""

    __abstract__ = True

    public_id: Mapped[UUID] = mapped_column(Uuid, server_default=text("gen_random_uuid()"))
