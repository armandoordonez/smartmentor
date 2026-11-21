"""``PostgresCourseMaterialReader`` against PostgreSQL (skipped without AI_TEST_DATABASE_URL).

The URL must point to a disposable database. The test creates ``course_materials`` with the
columns the reader uses (changelog ``v2.0.1-008``) in a private schema and leaves nothing behind.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.adapters.postgres.course_materials import ORIGIN_LICENSES, PostgresCourseMaterialReader

URL = os.environ.get("AI_TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(URL is None, reason="AI_TEST_DATABASE_URL is not set"),
]

DDL = """
DROP SCHEMA IF EXISTS mat_test CASCADE;
CREATE SCHEMA mat_test;
SET search_path TO mat_test, public;
CREATE TABLE course_materials (
  id bigserial PRIMARY KEY, course_id bigint NOT NULL, origin varchar(20) NOT NULL,
  file_name varchar(300), extracted_text text NOT NULL, active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now());
"""

INSERT = """
INSERT INTO course_materials (course_id, origin, file_name, extracted_text, active, created_at)
VALUES (:course, :origin, :name, :text, :active, now() - make_interval(mins => :age))
"""


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    assert URL is not None
    eng = create_async_engine(
        URL, connect_args={"server_settings": {"search_path": "mat_test,public"}}
    )
    async with eng.begin() as conn:
        for statement in [s for s in DDL.split(";") if s.strip()]:
            await conn.execute(text(statement))
    yield eng
    async with eng.begin() as conn:
        await conn.execute(text("DROP SCHEMA mat_test CASCADE"))
    await eng.dispose()


async def _add(
    engine: AsyncEngine,
    course: int,
    name: str,
    body: str,
    *,
    origin: str = "own_notes",
    active: bool = True,
    age: int = 0,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(INSERT),
            {
                "course": course,
                "origin": origin,
                "name": name,
                "text": body,
                "active": active,
                "age": age,
            },
        )


async def test_active_materials_with_text_are_sources_oldest_first(engine: AsyncEngine) -> None:
    await _add(engine, 1, "u2.pdf", "Regresión lineal", origin="open_license", age=5)
    await _add(engine, 1, "u1.md", "Aprendizaje supervisado", age=60)
    await _add(engine, 1, "retirado.pdf", "Ya no se usa", active=False)
    await _add(engine, 1, "vacio.txt", "   ")
    await _add(engine, 2, "otro.pdf", "Otro curso")

    first, second = await PostgresCourseMaterialReader(engine).sources(1)
    assert first.text == "Aprendizaje supervisado"
    assert first.title == "Apuntes del curso (u1.md)"
    assert first.license == ORIGIN_LICENSES["own_notes"]
    assert second.license == ORIGIN_LICENSES["open_license"]


async def test_course_without_materials_has_no_sources(engine: AsyncEngine) -> None:
    assert await PostgresCourseMaterialReader(engine).sources(9) == []
