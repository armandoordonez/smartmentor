"""Regresión: pedir un trabajo de IA no debe quedar bloqueado por la fila que la API tiene tomada.

`ai/` guarda cada trabajo en `ai_jobs` desde su propia conexión, con llaves foráneas a `courses`,
`topics` y `enrollments`. Si la API tiene esa fila con `SELECT ... FOR UPDATE` mientras espera la
respuesta de `ai/`, la validación de la llave foránea espera a la API y la API espera a `ai/`: a los
10 s la API responde `503 AI_SERVICE_UNAVAILABLE` y el trabajo queda huérfano (pasaba al enviar el
diagnóstico). Con `FOR NO KEY UPDATE` la fila sigue serializada y la llave foránea se valida.

`FakeAiService` no escribe en la base; `RowWritingAi` sí lo hace, como `ai/`. El caso del tema
(`topics`) está en `content/test_content_api.py`.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.main import app
from tests.integration.conftest import ClientFactory
from tests.integration.learning.helpers import (
    API,
    answer_attempt,
    enrollment_in_path,
    instructor_client,
    learner_client,
    publish_path,
    seed_items,
    start_attempt,
)
from tests.integration.row_writing_ai import RowWritingAi

pytestmark = pytest.mark.integration


async def test_ai_jobs_can_reference_the_rows_the_api_is_holding(
    client_for: ClientFactory, engine: AsyncEngine, setup_engine: AsyncEngine
) -> None:
    app.state.ai_service = RowWritingAi(setup_engine)

    # Curso: extracción del syllabus y publicación (bloquea `courses`).
    instructor = await instructor_client(client_for, engine)
    path = await publish_path(instructor)
    for topic_id in path.topics.values():
        await seed_items(engine, topic_id, "diagnostic", choices=1, correct="1")
        await seed_items(engine, topic_id, "topic_quiz", choices=4, short_answers=1)

    # Aprendiz: diagnóstico y quiz con respuesta corta (bloquean `enrollments`).
    learner = await learner_client(client_for, engine)
    enrollment_id = await enrollment_in_path(learner, path, diagnostic_correct={})
    route = (await learner.get(f"{API}/me/enrollments/{enrollment_id}/path")).json()
    step = next(s for s in route["steps"] if s["topic_id"] == path.fundamentals)
    attempt = await start_attempt(learner, enrollment_id, int(step["step_id"]))
    graded = await answer_attempt(learner, engine, attempt, correct=True)
    assert graded.json()["status"] == "graded"

    async with setup_engine.connect() as conn:
        rows = (await conn.execute(text("SELECT job_type, enrollment_id FROM ai_jobs"))).all()
    by_type = {row.job_type: row.enrollment_id for row in rows}
    assert by_type["grading.short_answer"] == enrollment_id
    assert by_type["diagnostic.finalize"] == enrollment_id
