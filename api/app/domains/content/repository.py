"""Interfaces (puertos) de los repositorios de contenido."""

from datetime import datetime
from typing import Any, Protocol

from app.domains.content.entities import (
    AssessmentItem,
    RatingSummary,
    Resource,
    VideoCandidate,
    VideoFeedback,
    VideoRelevanceJudgment,
)
from app.domains.learning_paths.entities import LearningPath


class ResourceRepository(Protocol):
    async def add(self, resource: Resource) -> Resource: ...

    async def get(self, resource_id: int) -> Resource | None: ...

    async def list_for_topic(self, topic_id: int) -> list[Resource]:
        """Recursos compartidos (`all_learners`) del tema, por tipo, versión e id."""
        ...

    async def latest_main_text(self, topic_id: int) -> Resource | None:
        """La versión más reciente del texto principal que no está retirada."""
        ...

    async def max_version(self, topic_id: int) -> int:
        """Mayor `version` del texto principal del tema (0 si no hay)."""
        ...

    async def exists_main_text_since(self, topic_id: int, moment: datetime) -> bool:
        """Hay un texto principal creado en o después de `moment` (idempotencia de la ingesta)."""
        ...

    async def update(self, resource_id: int, changes: dict[str, Any]) -> Resource | None: ...

    async def retire_other_approved(self, resource: Resource) -> None:
        """Retira los demás recursos aprobados del mismo tema, tipo y clase."""
        ...

    async def video_resource(self, video_candidate_id: int) -> Resource | None: ...

    async def lock_topic(self, topic_id: int) -> None:
        """Serializa la ingesta y la edición de los recursos de un tema."""
        ...


class ItemRepository(Protocol):
    async def add(self, item: AssessmentItem) -> AssessmentItem: ...

    async def get(self, item_id: int) -> AssessmentItem | None: ...

    async def get_for_update(self, item_id: int) -> AssessmentItem | None: ...

    async def search_topic(
        self,
        *,
        topic_id: int,
        source: str | None,
        review_status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AssessmentItem], int]: ...

    async def update(self, item_id: int, changes: dict[str, Any]) -> AssessmentItem | None: ...

    async def count_for_job(self, ai_job_id: int) -> int:
        """Ítems ya ingeridos de ese trabajo (idempotencia)."""
        ...

    async def resolve_ai_job_id(self, public_id: str) -> int | None: ...

    async def lock_topic(self, topic_id: int) -> None: ...

    async def exists(self, topic_id: int, source: str, stem: str) -> bool:
        """Ya hay un ítem activo con ese enunciado en ese banco del tema."""
        ...

    async def outcome_statements(self, topic_id: int) -> dict[int, str]:
        """Resultados de aprendizaje activos del tema: id -> enunciado."""
        ...


class VideoRepository(Protocol):
    async def add(self, video: VideoCandidate) -> VideoCandidate: ...

    async def get(self, video_id: int) -> VideoCandidate | None: ...

    async def get_by_youtube(
        self, topic_id: int, youtube_video_id: str
    ) -> VideoCandidate | None: ...

    async def list_for_topic(self, topic_id: int) -> list[VideoCandidate]:
        """Candidatos activos por `rank` (los sin rank al final) e id."""
        ...

    async def update(self, video_id: int, changes: dict[str, Any]) -> VideoCandidate | None: ...

    async def demote_in_use(self, topic_id: int, except_id: int) -> None:
        """Pasa a `backup` el video en uso del tema (solo hay uno)."""
        ...

    async def get_judgment(
        self, video_id: int, judge_user_id: int
    ) -> VideoRelevanceJudgment | None: ...

    async def save_judgment(
        self, video_id: int, judge_user_id: int, is_relevant: bool
    ) -> VideoRelevanceJudgment: ...

    async def judgments_of(self, judge_user_id: int, video_ids: list[int]) -> dict[int, bool]: ...


class FeedbackRepository(Protocol):
    async def find(self, video_id: int, enrollment_id: int) -> VideoFeedback | None: ...

    async def add(self, feedback: VideoFeedback) -> VideoFeedback: ...

    async def update(self, feedback_id: int, changes: dict[str, Any]) -> VideoFeedback | None: ...

    async def summaries(self, video_ids: list[int]) -> dict[int, RatingSummary]: ...


class EnrollmentLookup(Protocol):
    """Lectura mínima de inscripciones (las escribe el dominio `learning_paths`)."""

    async def course_of_learner_enrollment(self, enrollment_id: int, user_id: int) -> int | None:
        """`course_id` de la inscripción activa del aprendiz, o `None` si no es suya."""
        ...


class PathLookup(Protocol):
    async def get(self, path_id: int) -> LearningPath | None: ...
