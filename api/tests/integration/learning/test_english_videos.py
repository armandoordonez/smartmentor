"""R-001: el video en inglés solo se muestra a quien declara inglés B1 o superior (E6)."""

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.conftest import ClientFactory
from tests.integration.learning.helpers import (
    API,
    enrollment_in_path,
    instructor_client,
    learner_client,
    publish_path,
    seed_items,
)


async def _topic_video(
    http: httpx.AsyncClient, enrollment_id: int, topic_id: int
) -> dict[str, object]:
    steps = (await http.get(f"{API}/me/enrollments/{enrollment_id}/path")).json()["steps"]
    step_id = next(s["step_id"] for s in steps if s["topic_id"] == topic_id)
    content = await http.get(f"{API}/me/enrollments/{enrollment_id}/steps/{step_id}/content")
    assert content.status_code == 200, content.text
    video = content.json()["video"]
    assert isinstance(video, dict)
    return video


async def test_english_topic_video_depends_on_the_learner_english_level(
    client_for: ClientFactory, engine: AsyncEngine
) -> None:
    instructor = await instructor_client(client_for, engine)
    path = await publish_path(instructor)
    for topic_id in path.topics.values():
        await seed_items(engine, topic_id, "diagnostic", choices=1, correct="1")
        await seed_items(engine, topic_id, "topic_quiz", choices=4, short_answers=1)
    in_use = "ENGLISH0001"
    async with engine.begin() as conn:
        # El video del tema está en inglés; los dos respaldos, en español.
        for rank, (video_id, language, status) in enumerate(
            [
                (in_use, "en", "in_use"),
                ("SPANISH0001", "es", "backup"),
                ("SPANISH0002", "es", "backup"),
            ],
            start=1,
        ):
            await conn.execute(
                text(
                    "INSERT INTO video_candidates (topic_id, youtube_video_id, title, "
                    "duration_seconds, language, similarity, rank, status, origin) "
                    "VALUES (:t, :v, :title, 600, :lang, 0.8, :rank, :status, 'youtube_api')"
                ),
                {
                    "t": path.fundamentals,
                    "v": video_id,
                    "title": f"Video {video_id}",
                    "lang": language,
                    "rank": rank,
                    "status": status,
                },
            )

    spanish_only = await learner_client(client_for, engine, "ana")
    bilingual = await learner_client(client_for, engine, "beto")
    saved = await bilingual.put(
        f"{API}/me/profile",
        json={
            "description": "Ingeniero de datos; leo documentación técnica en inglés.",
            "languages": [{"code": "es", "cefr_level": "C2"}, {"code": "en", "cefr_level": "B2"}],
        },
    )
    assert saved.status_code == 200, saved.text

    ana = await enrollment_in_path(spanish_only, path, diagnostic_correct={})
    beto = await enrollment_in_path(bilingual, path, diagnostic_correct={})

    for_ana = await _topic_video(spanish_only, ana, path.fundamentals)
    for_beto = await _topic_video(bilingual, beto, path.fundamentals)
    assert for_beto["youtube_video_id"] == in_use
    assert for_beto["is_backup"] is False
    assert for_ana["youtube_video_id"] == "SPANISH0001"
    assert for_ana["is_backup"] is True
