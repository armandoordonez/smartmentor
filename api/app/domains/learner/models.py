"""Modelo de `survey_responses` (encuesta final y SUS, E13a y E13b).

La tabla la usa también el dominio del piloto: el modelo declara `extend_existing` para convivir
con otra declaración. `interaction_events` no tiene modelo: es de solo inserción y sin `_audit`, y se
escribe con SQL explícito (ver `repository_impl.py`).
"""

from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import BigInteger, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import PublicTableModel


class SurveyResponseModel(PublicTableModel):
    __tablename__ = "survey_responses"
    __table_args__: ClassVar[dict[str, Any]] = {"extend_existing": True}

    enrollment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("enrollments.id"))
    survey_type: Mapped[str] = mapped_column(String(10), server_default="final")
    likert: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    sus_items: Mapped[list[Any] | None] = mapped_column(JSONB)
    sus_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    comment: Mapped[str | None] = mapped_column(Text)
