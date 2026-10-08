"""«Mi ruta» (E5), el tema (E6) y «Mi progreso» (E11).

Une los pasos de la ruta con los nombres de sus temas. Los estados, intentos y puntajes vienen de
la API; aquí solo se agrupan y se cuentan para mostrarlos.
"""

from dataclasses import dataclass

from clients.base import ApiError, SmartMentorClient
from clients.models import (
    Enrollment,
    LearningPath,
    PathProgress,
    PathStep,
    Quiz,
    Topic,
    TopicContent,
)


@dataclass(frozen=True)
class StepView:
    topic: Topic
    step: PathStep


@dataclass(frozen=True)
class PathView:
    path: LearningPath
    enrollment: Enrollment
    progress: PathProgress
    steps: tuple[StepView, ...]

    @property
    def done_count(self) -> int:
        return sum(s.step.status in ("skipped", "approved") for s in self.steps)

    @property
    def skipped_count(self) -> int:
        return sum(s.step.status == "skipped" for s in self.steps)

    @property
    def current(self) -> StepView | None:
        return next((s for s in self.steps if s.step.status == "in_progress"), None)

    @property
    def completion(self) -> float:
        return self.done_count / len(self.steps) if self.steps else 0.0


@dataclass(frozen=True)
class TopicPage:
    path: PathView
    topic: Topic
    position: int
    content: TopicContent
    quiz: Quiz


@dataclass(frozen=True)
class ProgressOverview:
    paths: tuple[PathView, ...]
    done_topics: int
    total_topics: int
    attempts_per_topic: float
    saved_minutes: int


class LearningPathService:
    def __init__(self, client: SmartMentorClient) -> None:
        self._client = client

    def path_view(self, enrollment: Enrollment) -> PathView:
        path = self._client.get_learning_path(enrollment.learning_path_id)
        topics = {t.id: t for t in self._client.list_topics(path.course_id)}
        progress = self._client.get_path_progress(enrollment.id)
        return PathView(
            path=path,
            enrollment=enrollment,
            progress=progress,
            steps=tuple(StepView(topic=topics[s.topic_id], step=s) for s in progress.steps),
        )

    def topic_page(self, enrollment: Enrollment, topic_id: int) -> TopicPage:
        view = self.path_view(enrollment)
        found = next(
            ((i, s) for i, s in enumerate(view.steps, start=1) if s.topic.id == topic_id), None
        )
        if found is None:
            raise ApiError(404, "NOT_FOUND", "El tema no es parte de tu ruta")
        position, step = found
        return TopicPage(
            path=view,
            topic=step.topic,
            position=position,
            content=self._client.get_topic_content(topic_id),
            quiz=self._client.get_topic_quiz(enrollment.id, topic_id),
        )

    def progress_overview(self) -> ProgressOverview:
        views = tuple(
            self.path_view(e)
            for e in self._client.list_my_enrollments()
            if e.status in ("in_progress", "completed")
        )
        steps = [s.step for v in views for s in v.steps]
        attempted = [s.attempts_used for s in steps if s.attempts_used]
        return ProgressOverview(
            paths=views,
            done_topics=sum(s.status in ("skipped", "approved") for s in steps),
            total_topics=len(steps),
            attempts_per_topic=sum(attempted) / len(attempted) if attempted else 0.0,
            saved_minutes=sum(v.progress.saved_minutes for v in views),
        )
