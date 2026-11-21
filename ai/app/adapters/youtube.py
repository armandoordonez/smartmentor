"""``YouTubeSearchProvider``: YouTube Data API v3 behind ``VideoSearchProvider`` (plan 5.4.9).

Two calls per search: ``search.list`` (``relevanceLanguage``, ``videoEmbeddable=true``) for the
ids and ``videos.list`` for duration, language and description. Only metadata is read: captions
are not downloaded (DEF-07, P-06). The API key travels as the ``key`` query parameter, as the API
requires; it is never logged and errors do not repeat the URL.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.domain.video_ranking import parse_iso_duration
from app.ports.video import VideoSearchHit, VideoSearchQuery, VideoSearchUnavailableError

logger = logging.getLogger("app.youtube")

BASE_URL = "https://www.googleapis.com/youtube/v3"
MIN_CHAPTERS = 3
MAX_CHAPTERS = 20

_CHAPTER = re.compile(
    r"^\s*\(?((?:\d{1,2}:)?\d{1,2}:\d{2})\)?[\s:\-\u2013\u2014]+(?P<title>\S.*?)\s*$"
)


def parse_chapters(description: str) -> list[str]:
    """Chapter titles of a description (timestamps lines starting at 0:00), or an empty list."""
    found: list[tuple[str, str]] = []
    for line in description.splitlines():
        match = _CHAPTER.match(line)
        if match:
            found.append((match.group(1), match.group("title")))
    if len(found) < MIN_CHAPTERS or found[0][0] not in ("0:00", "00:00"):
        return []
    return [title for _, title in found[:MAX_CHAPTERS]]


def _language(snippet: dict[str, Any]) -> str | None:
    raw = snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage")
    if not isinstance(raw, str) or len(raw) < 2:
        return None
    code = raw[:2].lower()
    return code if code.isalpha() else None


class YouTubeSearchProvider:
    def __init__(
        self,
        api_key: str,
        client: httpx.AsyncClient,
        *,
        base_url: str = BASE_URL,
    ) -> None:
        self._key = api_key
        self._client = client
        self._base = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "youtube"

    async def _get(self, path: str, params: dict[str, str | int]) -> dict[str, Any]:
        try:
            response = await self._client.get(
                f"{self._base}/{path}", params={**params, "key": self._key}
            )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            raise VideoSearchUnavailableError(
                f"YouTube answered {exc.response.status_code} on {path}"
            ) from None
        except (httpx.HTTPError, ValueError) as exc:
            raise VideoSearchUnavailableError(
                f"YouTube request failed on {path}: {exc.__class__.__name__}"
            ) from None
        if not isinstance(body, dict):
            raise VideoSearchUnavailableError(f"YouTube answered an unexpected body on {path}")
        return body

    async def search(self, query: VideoSearchQuery) -> list[VideoSearchHit]:
        found = await self._get(
            "search",
            {
                "part": "snippet",
                "type": "video",
                "q": query.text,
                "maxResults": min(max(query.max_results, 1), 50),
                "relevanceLanguage": query.language,
                "safeSearch": "moderate",
                **({"videoEmbeddable": "true"} if query.embeddable_only else {}),
            },
        )
        ids = [
            item["id"]["videoId"]
            for item in found.get("items", [])
            if isinstance(item.get("id"), dict) and item["id"].get("videoId")
        ]
        if not ids:
            return []
        details = await self._get(
            "videos",
            {"part": "snippet,contentDetails", "id": ",".join(ids), "maxResults": len(ids)},
        )
        by_id = {item["id"]: item for item in details.get("items", []) if "id" in item}
        hits: list[VideoSearchHit] = []
        for video_id in ids:
            item = by_id.get(video_id)
            if item is None:
                continue
            snippet = item.get("snippet", {})
            if snippet.get("liveBroadcastContent", "none") != "none":
                continue
            description = str(snippet.get("description", ""))
            hits.append(
                VideoSearchHit(
                    youtube_video_id=video_id,
                    title=str(snippet.get("title", "")),
                    channel_title=str(snippet.get("channelTitle", "")),
                    description=description,
                    duration_seconds=parse_iso_duration(
                        str(item.get("contentDetails", {}).get("duration", ""))
                    ),
                    language=_language(snippet),
                    published_at=snippet.get("publishedAt"),
                    chapters=parse_chapters(description),
                )
            )
        logger.info("youtube search", extra={"results": len(hits)})
        return hits
