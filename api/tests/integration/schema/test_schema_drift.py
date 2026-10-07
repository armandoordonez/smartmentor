"""Detecta si los modelos SQLAlchemy se desalinean del esquema creado por Liquibase."""

import warnings

import pytest
from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

import app.domains.assessments.models
import app.domains.content.models
import app.domains.courses.models
import app.domains.identity.models
import app.domains.learning_paths.models
import app.domains.observability.models  # noqa: F401  (registra los modelos en Base.metadata)
from app.common.models import Base

pytestmark = pytest.mark.integration


def _compare(sync_conn: Connection) -> list[str]:
    problems: list[str] = []
    inspector = inspect(sync_conn)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # el tipo vector no es reconocido por la reflexión
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                problems.append(f"falta la tabla {table.name}")
                continue
            db_columns = {c["name"]: c for c in inspector.get_columns(table.name)}
            for column in table.columns:
                db_column = db_columns.get(column.name)
                if db_column is None:
                    problems.append(f"{table.name}.{column.name} no existe en la base")
                elif column.nullable != db_column["nullable"] and not column.primary_key:
                    problems.append(f"{table.name}.{column.name} difiere en nulabilidad")
            for name in db_columns:
                if name not in table.columns:
                    problems.append(f"{table.name}.{name} existe en la base pero no en el modelo")
    return problems


async def test_models_match_the_liquibase_schema(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        problems = await conn.run_sync(_compare)
    assert not problems, "\n".join(problems)


async def test_every_business_table_has_an_audit_table(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        tables = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    for table in Base.metadata.sorted_tables:
        assert f"{table.name}_audit" in tables, f"{table.name} no tiene tabla de auditoría"
