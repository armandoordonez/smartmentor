"""D4 · Detalle de aprendiz, D4b · Intentos agotados y D4c · Habilitar nuevos intentos.

Solo se ve a quien está inscrito en una ruta del instructor (la API responde 404 si no). El perfil
es el reducido de A3c. «Habilitar nuevos intentos» crea un permiso (`attempt-grants`) que la API
cuenta aparte de los 3 intentos de la regla.
"""

from zoneinfo import ZoneInfo

import streamlit as st

from clients.base import ApiError
from clients.models_staff import ExhaustedStep, LearnerDetail
from components.formatting import percent_points, short_date
from components.layout import render_notice, render_page_header_with_actions
from components.levels import LevelRow, render_level_bars
from components.staff_theme import ADMIN_ENROLLMENT_BADGE
from components.table import Row, render_table
from components.theme import ATTEMPT_BADGE, EDUCATION_LEVEL_LABEL, EXPERIENCE_BAND_LABEL
from core.config import get_settings
from core.container import get_client
from core.staff_errors import show_staff_error
from core.staff_state import CONTENT_REVIEW, PATH_DASHBOARD, get_staff_state

FINAL = -1


def _continue_text(step: ExhaustedStep) -> str:
    if not step.continue_topic_names:
        return ""
    return " El aprendiz puede seguir con " + ", ".join(step.continue_topic_names) + "."


def _profile_text(detail: LearnerDetail) -> str:
    """El resumen del fixture o, con la API real, el perfil reducido (A3c) en una línea."""
    if detail.profile_summary:
        return detail.profile_summary
    parts = [
        detail.job_title or "",
        EDUCATION_LEVEL_LABEL[detail.education_level] if detail.education_level else "",
        (
            f"Experiencia: {EXPERIENCE_BAND_LABEL[detail.experience_band].lower()}"
            if detail.experience_band
            else ""
        ),
    ]
    return " · ".join(part for part in parts if part) or "Sin descripción."


def _objective_text(detail: LearnerDetail) -> str:
    o = detail.objective
    if o is None:
        return ""
    return f"Objetivo: {o.bloom_verb.lower()} {o.content}, {o.criterion}."


client = get_client()
state = get_staff_state()
zone = ZoneInfo(get_settings().app_timezone)

if st.button("‹ Volver a la ruta", type="tertiary", key="ld-back"):
    st.switch_page(PATH_DASHBOARD)
render_notice("Privacidad: ves el perfil y los intentos solo de aprendices inscritos en TUS rutas.")

if state.path_id is None or state.enrollment_id is None:
    st.info("Elige un aprendiz desde «Rutas y avance».")
    st.stop()
try:
    detail: LearnerDetail = client.get_learner_detail(state.path_id, state.enrollment_id)
except ApiError as error:
    show_staff_error(error)
    st.stop()

exhausted = detail.exhausted_steps
if exhausted:
    step = exhausted[0]
    with st.container(border=True, key="panel-exhausted"):
        st.badge("Intentos agotados", color="orange")
        best = f" · mejor puntaje {percent_points(step.best_score)}" if step.best_score else ""
        st.markdown(
            f"**{step.topic_name}** · {step.attempts_used} de {step.max_attempts} intentos "
            f"usados{best}"
        )
        st.caption(
            f"Los temas que dependen de {step.topic_name} y la evaluación final quedan en "
            f"espera.{_continue_text(step)}"
        )
        if st.button("Habilitar nuevos intentos", type="primary", key="ld-grant"):
            st.session_state["ld-target"] = step.step_id

status_text = (
    "En espera por intentos agotados" if exhausted else ADMIN_ENROLLMENT_BADGE[detail.status][0]
)
group = f" · {detail.learning_path.group_label}" if detail.learning_path.group_label else ""
with render_page_header_with_actions(
    detail.user.full_name, caption=f"{detail.learning_path.name}{group} · {status_text}"
):
    if st.button("Corregir recurso", key="ld-fix"):
        first = detail.topic_levels[0].topic_id if detail.topic_levels else None
        state.topic_id = first
        st.switch_page(CONTENT_REVIEW)
    if st.button("Reiniciar intentos", type="primary", key="ld-reset"):
        st.session_state["ld-target"] = exhausted[0].step_id if exhausted else FINAL


def _grant_panel(target: int) -> None:
    """D4c · Habilitar nuevos intentos."""
    step: ExhaustedStep | None = next((s for s in exhausted if s.step_id == target), None)
    with st.container(border=True, key="panel-grant"):
        st.subheader("Habilitar nuevos intentos", anchor=False)
        if step:
            used = f"{step.attempts_used} de {step.max_attempts} intentos usados"
            best = f" (mejor puntaje {percent_points(step.best_score)})" if step.best_score else ""
            st.caption(f"{detail.user.full_name} · {step.topic_name} · {used}{best}")
        else:
            st.caption(f"{detail.user.full_name} · Evaluación final")
        attempts = st.selectbox("Intentos que se habilitan", [1, 2, 3, 4, 5], index=0, key="ld-n")
        note = st.text_area("Nota para el aprendiz (opcional)", key="ld-note")
        max_attempts = step.max_attempts if step else 3
        st.caption(
            "Cada intento trae preguntas nuevas. El reinicio queda en el historial y se reporta "
            "aparte en las métricas de intentos por tema, para no mezclarlo con los "
            f"{max_attempts} intentos de la regla."
        )
        with st.container(horizontal=True):
            cancel = st.button("Cancelar", key="ld-grant-cancel")
            save = st.button("Habilitar intentos", type="primary", key="ld-grant-ok")
    if cancel:
        st.session_state.pop("ld-target", None)
        st.rerun()
    if save:
        try:
            if step:
                client.grant_step_attempts(step.step_id, int(attempts or 1), note.strip() or None)
            else:
                client.grant_final_attempts(
                    detail.enrollment_id, int(attempts or 1), note.strip() or None
                )
        except ApiError as error:
            show_staff_error(error)
            return
        st.session_state.pop("ld-target", None)
        st.toast("Intentos habilitados")
        st.rerun()


if (target := st.session_state.get("ld-target")) is not None:
    _grant_panel(target)

# Perfil y nivel lado a lado, cada uno en su tarjeta, como Figma D4 (V-021).
profile_col, levels_col = st.columns(2)
with profile_col.container(border=True, key="card-learner-profile"):
    st.caption("**PERFIL Y OBJETIVO**")
    st.markdown(_profile_text(detail))
    # La API no manda la hoja de vida (perfil reducido A3c): sin dato no se afirma que falte.
    if detail.resume_summary:
        st.markdown(f"Hoja de vida: {detail.resume_summary}")
    if detail.objective:
        st.markdown(_objective_text(detail))
with levels_col.container(border=True, key="card-learner-levels"):
    st.caption("**NIVEL POR TEMA (DIAGNÓSTICO)**")
    render_level_bars(
        [LevelRow(t.topic_id, t.name, t.level * 100, t.classification) for t in detail.topic_levels]
    )

rows = [
    Row(
        key=str(attempt.attempt_id),
        cells=[
            attempt.topic_name + (" · intento extra" if attempt.extra_grant else ""),
            str(attempt.attempt_number),
            percent_points(attempt.score),
            ATTEMPT_BADGE[attempt.passed],
            short_date(attempt.submitted_at.astimezone(zone).date()),
        ],
    )
    for attempt in detail.attempts
]
render_table(
    ["Tema", "Intento", "Puntaje", "Resultado", "Fecha"],
    [3, 1, 1, 2, 2],
    rows,
    key="attempts",
    empty_text="Todavía no presentó intentos.",
)
