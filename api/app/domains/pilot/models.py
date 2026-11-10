"""Modelo SQLAlchemy del piloto. Refleja la tabla `pilots` del esquema v2.0.0 (Liquibase)."""

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import PublicTableModel


class PilotModel(PublicTableModel):
    __tablename__ = "pilots"

    learning_path_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_paths.id"))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    delayed_posttest_on: Mapped[date | None] = mapped_column(Date)
    random_seed: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(15), server_default="draft")
