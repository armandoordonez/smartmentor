"""YouTube, metadata transcripts, Gemini embeddings and the in-memory knowledge store."""

from __future__ import annotations

import httpx
import pytest

from app.adapters.memory_knowledge import InMemoryKnowledgeStore
from app.adapters.metadata_transcripts import MetadataTranscriptProvider
from app.adapters.youtube import YouTubeSearchProvider, parse_chapters
from app.application.embeddings.chunking import Chunk
from app.application.embeddings.store import SourceMaterial
from app.ports.video import VideoSearchHit, VideoSearchQuery, VideoSearchUnavailableError

KEY = "test-only-not-a-secret"


def youtube_transport(
    seen: list[httpx.Request], *, search_status: int = 200, live: bool = False
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/search"):
            if search_status != 200:
                return httpx.Response(search_status, json={"error": {"message": "quota"}})
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"id": {"videoId": "aaaaaaaaaaa"}},
                        {"id": {"videoId": "bbbbbbbbbbb"}},
                    ]
                },
            )
        description = "Intro\n0:00 Inicio\n1:10 Sigmoide\n5:00 Umbral\nSuscríbete"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "aaaaaaaaaaa",
                        "snippet": {
                            "title": "Sigmoide",
                            "channelTitle": "Canal",
                            "description": description,
                            "defaultAudioLanguage": "es-419",
                            "publishedAt": "2025-01-01T00:00:00Z",
                            "liveBroadcastContent": "live" if live else "none",
                        },
                        "contentDetails": {"duration": "PT9M30S"},
                    },
                    {
                        "id": "bbbbbbbbbbb",
                        "snippet": {"title": "Sin idioma", "description": ""},
                        "contentDetails": {"duration": "PT1H"},
                    },
                ]
            },
        )

    return httpx.MockTransport(handler)


async def test_youtube_search_sends_language_and_embeddable_and_reads_details() -> None:
    seen: list[httpx.Request] = []
    async with httpx.AsyncClient(transport=youtube_transport(seen)) as client:
        provider = YouTubeSearchProvider(KEY, client)
        hits = await provider.search(VideoSearchQuery(text="regresión logística", language="es"))
    search = seen[0].url.params
    assert search["relevanceLanguage"] == "es"
    assert search["videoEmbeddable"] == "true"
    assert search["type"] == "video"
    assert [h.youtube_video_id for h in hits] == ["aaaaaaaaaaa", "bbbbbbbbbbb"]
    first, second = hits
    assert first.duration_seconds == 570
    assert first.language == "es"
    assert first.chapters == ["Inicio", "Sigmoide", "Umbral"]
    assert second.language is None
    assert second.duration_seconds == 3600


async def test_youtube_can_search_without_the_embeddable_filter() -> None:
    seen: list[httpx.Request] = []
    async with httpx.AsyncClient(transport=youtube_transport(seen)) as client:
        await YouTubeSearchProvider(KEY, client).search(
            VideoSearchQuery(text="x", embeddable_only=False)
        )
    assert "videoEmbeddable" not in seen[0].url.params


async def test_live_broadcasts_are_left_out() -> None:
    async with httpx.AsyncClient(transport=youtube_transport([], live=True)) as client:
        hits = await YouTubeSearchProvider(KEY, client).search(VideoSearchQuery(text="x"))
    assert [h.youtube_video_id for h in hits] == ["bbbbbbbbbbb"]


async def test_a_quota_error_is_video_search_unavailable_and_does_not_leak_the_key() -> None:
    async with httpx.AsyncClient(transport=youtube_transport([], search_status=403)) as client:
        with pytest.raises(VideoSearchUnavailableError) as raised:
            await YouTubeSearchProvider(KEY, client).search(VideoSearchQuery(text="x"))
    assert KEY not in str(raised.value)
    assert "403" in str(raised.value)


async def test_a_network_error_is_video_search_unavailable() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
        with pytest.raises(VideoSearchUnavailableError):
            await YouTubeSearchProvider(KEY, client).search(VideoSearchQuery(text="x"))


def test_chapters_need_three_timestamps_from_zero() -> None:
    assert parse_chapters("0:00 A\n1:00 B\n2:00 C") == ["A", "B", "C"]
    assert parse_chapters("0:00 A\n1:00 B") == []
    assert parse_chapters("1:00 A\n2:00 B\n3:00 C") == []
    assert parse_chapters("00:00 - Intro\n01:30 – Tema\n1:02:03 Cierre") == [
        "Intro",
        "Tema",
        "Cierre",
    ]


async def test_metadata_transcript_is_title_chapters_and_description() -> None:
    hit = VideoSearchHit(
        "aaaaaaaaaaa", "Título", "Canal", "Descripción larga", 600, "es", chapters=["Uno", "Dos"]
    )
    transcript = await MetadataTranscriptProvider().transcript(hit)
    assert transcript.source == "metadata"
    assert transcript.text == "Título Capítulos: Uno; Dos. Descripción larga"


# ---------- in-memory knowledge store ----------


async def store_with_two_sources() -> InMemoryKnowledgeStore:
    store = InMemoryKnowledgeStore()
    await store.save_source(
        1,
        SourceMaterial("Apuntes", "x", url="https://example.org/a", license="CC0"),
        "sha-a",
        [Chunk(0, "cerca", 1), Chunk(1, "lejos", 1)],
        [[1.0, 0.0], [0.0, 1.0]],
        "m1",
    )
    await store.save_source(
        2, SourceMaterial("Otro curso", "y"), "sha-b", [Chunk(0, "ajeno", 1)], [[1.0, 0.0]], "m1"
    )
    return store


async def test_search_returns_the_closest_chunks_of_the_course_only() -> None:
    store = await store_with_two_sources()
    found = await store.search(1, [0.9, 0.1], "m1", 4)
    assert [c.text for c in found] == ["cerca", "lejos"]
    assert found[0].title == "Apuntes" and found[0].license == "CC0"
    assert found[0].score > found[1].score
    assert [c.text for c in await store.search(1, [0.9, 0.1], "m1", 1)] == ["cerca"]


async def test_vectors_of_another_model_are_never_compared() -> None:
    store = await store_with_two_sources()
    assert await store.search(1, [1.0, 0.0], "m2", 4) == []
    assert await store.has_source(1, "sha-a", "m1")
    assert not await store.has_source(1, "sha-a", "m2")
    assert not await store.has_source(1, "sha-zzz", "m1")


async def test_chunks_by_ids_keep_the_requested_order() -> None:
    store = await store_with_two_sources()
    found = await store.chunks_by_ids(["2", "1", "999"])
    assert [c.text for c in found] == ["lejos", "cerca"]


async def test_topic_vectors_remember_their_content_hash() -> None:
    store = InMemoryKnowledgeStore()
    assert await store.vector_sha("topic", 1, "m1") is None
    await store.save_vector("topic", 1, "m1", [1.0], "abc")
    assert await store.vector_sha("topic", 1, "m1") == "abc"
    assert await store.vector_sha("topic", 1, "m2") is None
