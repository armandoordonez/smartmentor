"""Modelo de `learning_paths`: lo que necesita el dominio de cursos (`POST /courses` crea la ruta).

El dominio completo (rutas, inscripciones, pasos, secuenciación) lo implementa un agente posterior
sobre este mismo modelo, que ya refleja todas las columnas de la sección 5.2.1 del plan.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Numeric, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.models import UpdatableTableModel


class LearningPathModel(UpdatableTableModel):
    __tablename__ = "learning_paths"

    course_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("courses.id"))
    name: Mapped[str] = mapped_column(String(200))
    group_label: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    default_objective_bloom_verb: Mapped[str | None] = mapped_column(Text)
    default_objective_content: Mapped[str | None] = mapped_column(Text)
    default_objective_criterion: Mapped[str | None] = mapped_column(Text)
    topic_pass_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default="70")
    final_pass_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default="80")
    mastery_skip_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default="80")
    max_attempts: Mapped[int] = mapped_column(SmallInteger, server_default="3")
    level_weights: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text('\'{"test": 0.8, "profile": 0.1, "resume": 0.1}\'::jsonb')
    )
    short_answer_min_ratio: Mapped[Decimal] = mapped_column(Numeric(5, 4), server_default="0.6667")
