"""Estado de la sesión que comparten las páginas del aprendiz (F07b).

Se guarda dentro de `AppSession.learner` (en `st.session_state`, nunca en cachés compartidas).
Lo que la API dice (`next_action`) manda: aquí solo se recuerda a dónde iba la persona (el tema, el
intento, el trabajo de IA) y lo que aún no se ha guardado.
"""

from dataclasses import dataclass, field

from clients.base import ApiError
from clients.models import Job, LearnerAnswer


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
class LearnerState:
    step_id: int | None = None
    attempt_id: int | None = None
    job_id: str | None = None
    diagnostic_job_id: str | None = None
    quiz_job_id: str | None = None
    quiz_job_kind: str = "grade"
    final_attempt_id: int | None = None
    sheet: AnswerSheet = field(default_factory=AnswerSheet)
    finished_jobs: dict[str, Job] = field(default_factory=dict)
    job_polls: dict[str, int] = field(default_factory=dict)
    job_error: ApiError | None = None
    edit_objective: bool = False
    survey_step: int = 1
    survey_likert: dict[str, int] = field(default_factory=dict)
    survey_sus: dict[int, int] = field(default_factory=dict)
    manage_consents: bool = False

    def forget_position(self) -> None:
        """Olvida el tema, los intentos y los trabajos de la ruta anterior (B-027).

        Se llama al cambiar de inscripción: si no, la ruta nueva abría el tema o el intento de la
        otra. Los trabajos ya terminados se conservan porque se identifican por su id.
        """
        self.step_id = self.attempt_id = self.final_attempt_id = None
        self.job_id = self.diagnostic_job_id = self.quiz_job_id = None
        self.quiz_job_kind = "grade"
        self.edit_objective = False
        self.survey_step = 1
