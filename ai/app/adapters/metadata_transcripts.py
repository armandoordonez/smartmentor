"""``MetadataTranscriptProvider``: the «transcript» of a video is its title, description and
chapters (DEF-07: captions are not downloaded until the terms of the YouTube API are verified,
P-06). The source is recorded as ``metadata``."""

from __future__ import annotations

from app.ports.video import Transcript, VideoSearchHit

MAX_DESCRIPTION_CHARS = 1000


class MetadataTranscriptProvider:
    @property
    def name(self) -> str:
        return "metadata"

    async def transcript(self, video: VideoSearchHit) -> Transcript:
        parts = [video.title]
        if video.chapters:
            parts.append("Capítulos: " + "; ".join(video.chapters) + ".")
        if video.description:
            parts.append(video.description[:MAX_DESCRIPTION_CHARS])
        return Transcript(
            youtube_video_id=video.youtube_video_id,
            text=" ".join(p.strip() for p in parts if p.strip()),
            source="metadata",
        )
