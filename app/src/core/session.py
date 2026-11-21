"""Estado de la sesión de cada usuario, con sus claves en un solo lugar.

Todo lo personal vive aquí (en `st.session_state`), nunca en cachés compartidas. Las páginas leen y
escriben `AppSession`; los componentes no lo tocan: reciben sus datos por parámetro.

Un agente que agregue páginas suma aquí sus campos (con valor por omisión) y, si la página se
reinicia al entrar a otra ruta, un método `start_*` como `start_onboarding`.
"""

from dataclasses import dataclass, field
from typing import Literal

import streamlit as st

from clients.fixtures import FixturesClient
from clients.models import Me, Role
from core.learner_state import LearnerState

_KEY = "app_session"

ConsentStep = Literal["terms", "informed"]


@dataclass(frozen=True)
class PendingClick:
    """Clic que interrumpió la renovación del token: se repite en su página al volver (B-040)."""

    page: str
    widget_id: str
    key: str


@dataclass
class AppSession:
    # Identidad: `me` sale de GET /me (o del escenario en modo fixtures).
    me: Me | None = None
    active_role: Role | None = None
    scenario_key: str | None = None
    fixtures_client: FixturesClient | None = None

    # Consentimiento (A3, A3b)
    consent_step: ConsentStep = "terms"
    accept_data: bool = False
    accept_pilot: bool = False
    consent_done: bool = False

    # Aprendiz: catálogo e incorporación
    selected_path_id: int | None = None
    selected_enrollment_id: int | None = None
    extra_tools: list[str] = field(default_factory=list)

    # Aprendiz: diagnóstico, ruta, intentos y trabajos de IA (F07b)
    learner: LearnerState = field(default_factory=LearnerState)

    # Claves de idempotencia por operación, estables entre reejecuciones del mismo botón.
    idempotency_keys: dict[str, str] = field(default_factory=dict)

    # Renovación del token (B-030): la página de la última ejecución completa y, al volver de
    # Keycloak con la sesión recuperada, la página a la que hay que regresar.
    current_page: str | None = None
    resume_page: str | None = None
    # B-040: valores de los widgets de la página (con su `key`) y el clic que la renovación
    # interrumpió, para ponerlos de nuevo y repetirlo al volver.
    resume_drafts: dict[str, object] = field(default_factory=dict)
    resume_click: PendingClick | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.me is not None

    def start_onboarding(self, path_id: int, enrollment_id: int) -> None:
        """Empieza (o retoma) la incorporación a una ruta: la hoja de vida parte limpia."""
        if enrollment_id != self.selected_enrollment_id:
            self.learner.forget_position()
        self.selected_path_id = path_id
        self.selected_enrollment_id = enrollment_id
        self.extra_tools = []

    def switch_role(self, role: Role) -> None:
        """Cambia el rol activo (solo presentación, CU-35): la API autoriza por la unión."""
        if self.me is None or role not in self.me.roles:
            return
        self.active_role = role


def get_session() -> AppSession:
    if _KEY not in st.session_state:
        st.session_state[_KEY] = AppSession()
    session: AppSession = st.session_state[_KEY]
    return session


def reset_session() -> None:
    st.session_state[_KEY] = AppSession()


def replace_session(session: AppSession) -> None:
    """Pone una sesión recuperada (la que se aparcó antes de renovar el token, B-030)."""
    st.session_state[_KEY] = session
