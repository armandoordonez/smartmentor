"""``PostgresSyllabusSourceReader`` against PostgreSQL (skipped without AI_TEST_DATABASE_URL).

The URL must point to a disposable database. The test creates ``syllabus_documents`` with the
columns the reader uses (changelog ``011``) in a private schema and leaves nothing behind.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.adapters.postgres.syllabus_sources import SYLLABUS_LICENSE, PostgresSyllabusSourceReader

URL = os.environ.get("AI_TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(URL is None, reason="AI_TEST_DATABASE_URL is not set"),
]

DDL = """
DROP SCHEMA IF EXISTS syl_test CASCADE;
CREATE SCHEMA syl_test;
SET search_path TO syl_test, public;
CREATE TABLE syllabus_documents (
  id bigserial PRIMARY KEY, course_id bigint NOT NULL, source_type varchar(10) NOT NULL,
  file_name varchar(300), extracted_text text, active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now());
"""

INSERT = """
INSERT INTO syllabus_documents (course_id, source_type, file_name, extracted_text, active,
                                created_at)
VALUES (:course, 'pdf', :name, :text, :active, now() - make_interval(mins => :age))
"""


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    assert URL is not None
    eng = create_async_engine(
        URL, connect_args={"server_settings": {"search_path": "syl_test,public"}}
    )
    async with eng.begin() as conn:
        for statement in [s for s in DDL.split(";") if s.strip()]:
            await conn.execute(text(statement))
    yield eng
    async with eng.begin() as conn:
        await conn.execute(text("DROP SCHEMA syl_test CASCADE"))
    await eng.dispose()


async def _add(
    engine: AsyncEngine, course: int, name: str | None, body: str | None, *, active: bool, age: int
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(INSERT),
            {"course": course, "name": name, "text": body, "active": active, "age": age},
        )


async def test_latest_active_syllabus_with_text_is_the_source(engine: AsyncEngine) -> None:
    await _add(engine, 1, "viejo.pdf", "Syllabus anterior", active=True, age=60)
    await _add(engine, 1, "nuevo.pdf", "Syllabus vigente", active=True, age=10)
    await _add(engine, 1, "borrado.pdf", "Syllabus inactivo", active=False, age=1)
    await _add(engine, 1, "escaneado.pdf", "   ", active=True, age=0)
    await _add(engine, 2, "otro.pdf", "Otro curso", active=True, age=0)

    (material,) = await PostgresSyllabusSourceReader(engine).sources(1)
    assert material.text == "Syllabus vigente"
    assert material.title == "Syllabus del curso (nuevo.pdf)"
    assert material.license == SYLLABUS_LICENSE


async def test_pasted_syllabus_without_file_name_has_a_plain_title(engine: AsyncEngine) -> None:
    await _add(engine, 3, None, "Texto pegado", active=True, age=0)
    (material,) = await PostgresSyllabusSourceReader(engine).sources(3)
    assert material.title == "Syllabus del curso"


async def test_course_without_syllabus_text_has_no_sources(engine: AsyncEngine) -> None:
    await _add(engine, 4, "escaneado.pdf", None, active=True, age=0)
    assert await PostgresSyllabusSourceReader(engine).sources(4) == []
