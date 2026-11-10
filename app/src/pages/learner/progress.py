"""E11 · Mi progreso, E11b · Gestionar autorizaciones.

Muestra el avance de la inscripción (cifras de la API), las metas de estudio y la racha (si la API
las ofrece) y las autorizaciones sobre los datos: salir del piloto o revocar la autorización y
pedir la supresión (Ley 1581). «Continuar mi ruta» sigue el `next_action`.
"""

import streamlit as st

from clients.base import ApiError
from clients.models import Enrollment, PathDetail
from clients.models_learner import StudyGoals, StudyGoalsUpdate
from components.formatting import decimal, duration, short_date
from components.layout import render_notice, render_page_header
from components.stat_tiles import render_stat_tiles
from core.container import get_client
from core.errors import show_action_error
from core.identity import current_me, label_for, refresh_me
from core.learner_flow import current_enrollment, go_to_action
from core.session import get_session
from services.learning import step_name

DATA_RIGHTS_PAGE = "pages/common/data_rights.py"
RETENTION_PAGE = "pages/learner/retention_test.py"
ARM_LABEL = {"personalized": "ruta personalizada", "fixed": "ruta fija"}
LEAVE_PILOT = "Salir del piloto"
REVOKE_ALL = "Revocar la autorización y borrar mis datos"

client = get_client()
state = get_session().learner
me = current_me()
enrollment: Enrollment = current_enrollment(client)

try:
    path: PathDetail = client.get_path(enrollment.id)
    goals = client.get_study_goals()
except ApiError as error:
    show_action_error(error)
    st.stop()

role_label = label_for("learner")
render_notice(f"Tu rol: {role_label} · Solo ves tu propio avance, nunca el de otros aprendices.")
render_page_header("Mi progreso")

tried = [s.attempts_used for s in path.steps if s.attempts_used > 0]
progress = enrollment.progress
render_stat_tiles(
    [
        (f"{progress.steps_done} de {progress.steps_total}", "Temas aprobados"),
        (decimal(sum(tried) / len(tried)) if tried else "—", "Intentos por tema"),
        (duration(path.savings.skipped_minutes), "Ahorrados por diagnóstico"),
    ],
    key="progress",
)

with st.container(key="card-progress-route"):
    st.markdown(f"**{enrollment.learning_path.name}**")
    next_name = step_name(path, enrollment.next_action.step_id)
    if next_name:
        st.caption(f"Siguiente paso: {next_name}")
    if st.button("Continuar mi ruta", type="primary", key="progress-continue"):
        go_to_action(enrollment.next_action)


if enrollment.status == "completed":
    with st.container(key="card-retention"):
        st.markdown("**Prueba de retención disponible · opcional**")
        st.caption(
            "10 preguntas · unos 10 minutos. Nos ayuda a medir cuánto recuerdas semanas después "
            "de terminar la ruta."
        )
        if st.button("Empezar prueba", key="progress-retention"):
            st.switch_page(RETENTION_PAGE)


def _goals(current: StudyGoals) -> None:
    st.subheader("Mis metas · opcional", anchor=False)
    st.caption(
        "Lo que tú te propones hoy y este mes. Solo tú las ves y no cambian el objetivo de tu ruta."
    )
    st.markdown(f"**Racha de {current.streak_days} días**")
    today, month = st.columns(2)
    with today:
        st.markdown("**Hoy**")
        st.caption("minutos de estudio")
        st.markdown(f"## {current.daily_minutes_done}")
        st.caption(f"de {current.daily_minutes_goal} min")
        missing = max(current.daily_minutes_goal - current.daily_minutes_done, 0)
        if missing:
            st.caption(f"Faltan {missing} min")
        daily = st.segmented_control(
            "Meta:",
            current.daily_options,
            default=current.daily_minutes_goal,
            format_func=lambda minutes: f"{minutes} min",
            key="goal-daily",
        )
    with month:
        st.markdown("**Este mes**")
        st.caption("temas aprobados")
        st.markdown(f"## {current.monthly_topics_done}")
        st.caption(f"de {current.monthly_topics_goal} temas")
        left = max(current.monthly_topics_goal - current.monthly_topics_done, 0)
        if left:
            st.caption(f"Falta {left}" if left == 1 else f"Faltan {left}")
        monthly = st.segmented_control(
            "Meta:",
            current.monthly_options,
            default=current.monthly_topics_goal,
            format_func=str,
            key="goal-monthly",
        )
    if (daily, monthly) != (current.daily_minutes_goal, current.monthly_topics_goal) and (
        daily is not None and monthly is not None
    ):
        try:
            client.set_study_goals(
                StudyGoalsUpdate(daily_minutes_goal=daily, monthly_topics_goal=monthly)
            )
        except ApiError as error:
            show_action_error(error)
        else:
            st.rerun()


if goals is not None:
    _goals(goals)

# --- Tus datos y autorizaciones ------------------------------------------------------------------

status = me.consent_status
st.subheader("Tus datos y autorizaciones", anchor=False)
if status.data_processing.granted_at is not None:
    st.markdown(f"Datos: autorizado el {short_date(status.data_processing.granted_at.date())}")
if status.pilot_research.granted:
    arm = ARM_LABEL.get(enrollment.pilot_arm or "", "")
    st.markdown(f"Piloto: participas · {arm}" if arm else "Piloto: participas")
else:
    st.markdown("Piloto: no participas")
st.caption(
    "Puedes salir del piloto sin perder tu ruta ni tu badge, o revocar la autorización y pedir "
    "que borremos tus datos."
)
if st.button("Gestionar mis autorizaciones", key="consents-manage"):
    state.manage_consents = True
st.page_link(DATA_RIGHTS_PAGE, label="Tus derechos y quién ve cada dato →")

if state.manage_consents:
    # E11b · Gestionar autorizaciones
    with st.container(key="card-consents-manage", border=True):
        st.subheader("Gestionar mis autorizaciones", anchor=False)
        st.caption("Elige qué quieres cambiar. Puedes volver a autorizar más adelante.")
        options = [LEAVE_PILOT, REVOKE_ALL] if status.pilot_research.granted else [REVOKE_ALL]
        captions = {
            LEAVE_PILOT: "Tus datos dejan de entrar al análisis desde hoy. Sigues con tu ruta, "
            "tus intentos y tu badge.",
            REVOKE_ALL: "Cerramos tu cuenta y borramos tu hoja de vida, tu diagnóstico y tus "
            "intentos. Pierdes tu avance y no podrás descargar el badge.",
        }
        choice = st.radio(
            "Gestionar mis autorizaciones",
            options,
            captions=[captions[o] for o in options],
            index=None,
            label_visibility="collapsed",
            key="consents-choice",
        )
        with st.container(horizontal=True):
            if st.button("Cancelar", key="consents-cancel"):
                state.manage_consents = False
                st.rerun()
            confirm = st.button(
                "Confirmar", type="primary", key="consents-confirm", disabled=choice is None
            )
        if confirm:
            try:
                if choice == LEAVE_PILOT:
                    client.revoke_consent("pilot_research")
                else:
                    client.create_data_subject_request("deletion", "Solicitud desde Mi progreso")
                    client.revoke_consent("data_processing")
            except ApiError as error:
                show_action_error(error)
            else:
                state.manage_consents = False
                refresh_me()
                st.rerun()
