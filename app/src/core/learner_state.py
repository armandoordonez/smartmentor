"""Estado de la sesión que comparten las páginas del aprendiz (F07b).

Se guarda dentro de `AppSession.learner` (en `st.session_state`, nunca en cachés compartidas).
Lo que la API dice (`next_action`) manda: aquí solo se recuerda a dónde iba la persona (el tema, el
intento, el trabajo de IA) y lo que aún no se ha guardado.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from clients.base import ApiError
from clients.models import Job, LearnerAnswer
from clients.models_learner import InteractionEvent


@dataclass
class AnswerSheet:
    """Respuestas de un diagnóstico o intento, mientras se responden de una en una."""

    key: str = ""
    index: int = 0
    answers: dict[int, LearnerAnswer] = field(default_factory=dict)

    def load(self, key: str, saved: list[LearnerAnswer], total: int) -> None:
        """Parte de lo guardado en la API; sigue en la primera pregunta sin responder."""
        if self.key == key:
            return
        self.key = key
        self.answers = {answer.item_id: answer for answer in saved}
        self.index = min(len(self.answers), max(total - 1, 0))


@dataclass
class OpenView:
    """Una visita en curso a una pantalla medida (tema, ruta, quiz, final): cuándo empezó y qué
    evento la cierra con sus `seconds`."""

    page: str
    close_type: str
    enrollment_id: int
    topic_id: int | None
    payload: dict[str, Any]
    started_at: datetime


@dataclass
class UsageLog:
    """Eventos de uso de la sesión (m27): visitas abiertas, marcas de lo ya enviado y lo pendiente.

    - `current_page`: la página que se está dibujando (la pone `main.py` en cada ejecución).
    - `open_views`: visitas en curso, por pantalla y entidad (`topic:7:813`).
    - `sent`: marcas de los eventos que van una sola vez (`quiz.start:9002`).
    - `pending`: lote que no llegó porque la API no respondía; sale con el próximo envío.
    """

    current_page: str | None = None
    open_views: dict[str, OpenView] = field(default_factory=dict)
    sent: set[str] = field(default_factory=set)
    pending: list[InteractionEvent] = field(default_factory=list)


@dataclass(frozen=True)
class PendingAttempt:
    """Reintento del quiz pedido en E7b que la página del quiz todavía no creó (B-060).

    `key` es el nombre de la clave de idempotencia del intento y `number`, el número del intento
    nuevo (para el título de U1b).
    """

    key: str
    number: int


@dataclass
class LearnerState:
    step_id: int | None = None
    attempt_id: int | None = None
    job_id: str | None = None
    diagnostic_job_id: str | None = None
    quiz_job_id: str | None = None
    quiz_job_kind: str = "grade"
    # B-060: E7b deja aquí el reintento y el quiz lo pide con U1b ya en pantalla.
    pending_attempt: PendingAttempt | None = None
    final_attempt_id: int | None = None
    # Intento de la final que E9 acaba de abrir (reintento o «Continuar»): E8 lo muestra aunque la
    # inscripción leída todavía diga `review_final` (B-041). Se olvida al entregar o calificar.
    pending_final_attempt_id: int | None = None
    # E9 pidió el reintento y todavía no hay intento (se generan preguntas, B-011): la inscripción
    # sigue en `review_final` y E8 no debe devolver a E9 mientras tanto (B-048).
    awaiting_final_questions: bool = False
    sheet: AnswerSheet = field(default_factory=AnswerSheet)
    finished_jobs: dict[str, Job] = field(default_factory=dict)
    job_polls: dict[str, int] = field(default_factory=dict)
    job_error: ApiError | None = None
    edit_objective: bool = False
    survey_step: int = 1
    survey_likert: dict[str, int] = field(default_factory=dict)
    survey_sus: dict[int, int] = field(default_factory=dict)
    survey_comment: str = ""
    manage_consents: bool = False
    usage: UsageLog = field(default_factory=UsageLog)

    def forget_position(self) -> None:
        """Olvida el tema, los intentos y los trabajos de la ruta anterior (B-027).

        Se llama al cambiar de inscripción: si no, la ruta nueva abría el tema o el intento de la
        otra. Los trabajos ya terminados se conservan porque se identifican por su id.
        """
        self.step_id = self.attempt_id = self.final_attempt_id = None
        self.pending_final_attempt_id = None
        self.awaiting_final_questions = False
        self.job_id = self.diagnostic_job_id = self.quiz_job_id = None
        self.quiz_job_kind = "grade"
        self.pending_attempt = None
        self.edit_objective = False
        self.survey_step = 1
