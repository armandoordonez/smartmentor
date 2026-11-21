"""E11 · Mi progreso, E11b · Gestionar autorizaciones.

Muestra el avance de la inscripción (cifras de la API), las metas de estudio y la racha (si la API
las ofrece) y las autorizaciones sobre los datos: salir del piloto o revocar la autorización y
pedir la supresión (Ley 1581). «Continuar mi ruta» sigue el `next_action`.
"""

import streamlit as st

from clients.base import ApiError
from clients.models import Enrollment, PathDetail
from clients.models_learner import StudyGoals, StudyGoalsUpdate
from components.formatting import decimal, plural, short_date
from components.layout import render_notice, render_page_header
from components.stat_tiles import render_stat_tiles
from core import features
from core.container import get_client
from core.errors import show_action_error
from core.identity import current_me, label_for, refresh_me
from core.learner_flow import current_enrollment, go_to_action
from core.session import get_session
from core.widget_state import seed_defaults
from services.learning import savings_label, step_name

DATA_RIGHTS_PAGE = "pages/common/data_rights.py"
RETENTION_PAGE = "pages/learner/retention_test.py"
ARM_LABEL = {"personalized": "ruta personalizada", "fixed": "ruta fija"}
NO_GOAL_YET = "Aún no elegiste tu meta"
GOAL_MET = "Meta cumplida"
LEAVE_PILOT = "Salir del piloto"
REVOKE_ALL = "Revocar la autorización y borrar mis datos"
NO_GOALS = StudyGoals(
    daily_minutes_goal=0,
    daily_minutes_done=0,
    monthly_topics_goal=0,
    monthly_topics_done=0,
    streak_days=0,
)

client = get_client()
state = get_session().learner
me = current_me()
enrollment: Enrollment = current_enrollment(client)

try:
    enrollments = client.list_enrollments(limit=100).items
    path: PathDetail = client.get_path(enrollment.id)
    goals = client.get_study_goals()
except ApiError as error:
    show_action_error(error)
    st.stop()

role_label = label_for("learner")
render_notice(f"Tu rol: {role_label} · Solo ves tu propio avance, nunca el de otros aprendices.")
render_page_header("Mi progreso")

if len(enrollments) > 1:
    # B-037: con varias rutas se elige cuál mostrar. La clave lleva el id para que el selector
    # parta de la ruta vigente aunque otra pantalla (Logros) haya cambiado la elegida.
    names = {e.id: e.learning_path.name for e in enrollments}
    route_key = f"progress-route-{enrollment.id}"
    # Sin `index=`: la ruta vigente entra por el estado de sesión y no pisa un borrador (B-054).
    seed_defaults({route_key: enrollment.id if enrollment.id in names else next(iter(names))})
    chosen = st.selectbox(
        "Ruta",
        list(names),
        format_func=names.__getitem__,
        label_visibility="collapsed",
        key=route_key,
    )
    if chosen != enrollment.id:
        get_session().selected_enrollment_id = chosen
        st.rerun()

tried = [s.attempts_used for s in path.steps if s.attempts_used > 0]
progress = enrollment.progress
render_stat_tiles(
    [
        (f"{progress.steps_done} de {progress.steps_total}", "Temas aprobados"),
        (decimal(sum(tried) / len(tried)) if tried else "—", "Intentos por tema"),
        (savings_label(path), "Ahorrados por diagnóstico"),
    ],
    key="progress",
)

with st.container(key="card-progress-route"):
    st.markdown(f"**{enrollment.learning_path.name}**")
    # Siempre se dibuja la barra, también con 0 % (B-061): el riel vacío (ver progress.css) dice
    # «aún no hay avance»; un hueco parece un error.
    st.progress(
        min(progress.steps_done / progress.steps_total, 1.0) if progress.steps_total else 0.0
    )
    next_name = step_name(path, enrollment.next_action.step_id)
    if next_name:
        st.caption(f"Siguiente paso: {next_name}")
    if st.button("Continuar mi ruta", type="primary", key="progress-continue"):
        go_to_action(enrollment.next_action)


if features.RETENTION_AVAILABLE and enrollment.status == "completed":
    with st.container(key="card-retention"):
        st.markdown("**Prueba de retención disponible · opcional**")
        st.caption(
            "10 preguntas · unos 10 minutos. Nos ayuda a medir cuánto recuerdas semanas después "
            "de terminar la ruta."
        )
        if st.button("Empezar prueba", type="primary", key="progress-retention"):
            st.switch_page(RETENTION_PAGE)


def _goal_card(
    *,
    key: str,
    title: str,
    unit: str,
    done: int,
    goal: int,
    goal_text: str,
    missing_text: str,
    new: bool,
) -> None:
    """Subtarjeta de una meta: cifra con «de N» en línea, barra de avance y lo que falta."""
    with st.container(key=key):
        with st.container(horizontal=True):
            st.markdown(f"**{title}**")
            with st.container(key=f"goal-right-unit-{key}"):
                st.caption(unit)
        if new:
            # Sin meta elegida no hay cifra que mostrar: un «0» parecería un avance real.
            st.caption(NO_GOAL_YET)
            return
        # Con varias inscripciones lo hecho supera la meta («5 de 3»): se dice que se cumplió.
        if goal > 0 and done >= goal:
            missing_text = GOAL_MET
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.markdown(f"## {done}")
            st.caption(goal_text)
            if missing_text:
                with st.container(key=f"goal-right-missing-{key}"):
                    st.caption(missing_text)
        if goal > 0:
            st.progress(min(done / goal, 1.0))


def _goals(current: StudyGoals, *, new: bool) -> tuple[int | None, int | None]:
    """Metas del día y del mes; `new` cuando la persona aún no las ha elegido (sin preselección)."""
    st.subheader("Mis metas · opcional", anchor=False)
    st.caption(
        "Lo que tú te propones hoy y este mes. Solo tú las ves y no cambian el objetivo de tu ruta."
    )
    if new:
        st.caption("Todavía no tienes metas. Elige una para hoy y otra para este mes.")
    else:
        st.badge(f"Racha de {plural(current.streak_days, 'día', 'días')}", color="gray")
    if not new:
        # Sin `default=`: las metas guardadas entran por el estado de sesión y no pisan un
        # borrador restaurado (B-054). Con `new` no hay preselección.
        seed_defaults(
            {"goal-daily": current.daily_minutes_goal, "goal-monthly": current.monthly_topics_goal}
        )
    today, month = st.columns(2)
    missing = max(current.daily_minutes_goal - current.daily_minutes_done, 0)
    left = max(current.monthly_topics_goal - current.monthly_topics_done, 0)
    with today:
        _goal_card(
            key="goal-card-today",
            title="Hoy",
            unit="minutos de estudio",
            done=current.daily_minutes_done,
            goal=current.daily_minutes_goal,
            goal_text=f"de {current.daily_minutes_goal} min",
            missing_text=f"Faltan {missing} min" if missing else "",
            new=new,
        )
        daily = st.segmented_control(
            "Meta:",
            current.daily_options,
            format_func=lambda minutes: f"{minutes} min",
            key="goal-daily",
        )
    with month:
        _goal_card(
            key="goal-card-month",
            title="Este mes",
            unit="temas aprobados",
            done=current.monthly_topics_done,
            goal=current.monthly_topics_goal,
            goal_text=f"de {current.monthly_topics_goal} temas",
            missing_text=(f"Falta {left}" if left == 1 else f"Faltan {left}") if left else "",
            new=new,
        )
        monthly = st.segmented_control(
            "Meta:",
            current.monthly_options,
            format_func=str,
            key="goal-monthly",
        )
    return daily, monthly


# El cliente da `None` mientras la persona no tenga metas (la API responde 200 con metas en 0, o
# 404 en versiones anteriores); antes la sección no se mostraba y nunca se podían elegir (B-028).
# Sin metas se muestra vacía, con las opciones por omisión (también si llega un 200 vacío crudo).
has_goals = goals is not None and not goals.is_empty
current_goals = goals if goals is not None and has_goals else NO_GOALS
with st.container(key="card-goals"):
    daily, monthly = _goals(current_goals, new=not has_goals)
if (daily, monthly) != (current_goals.daily_minutes_goal, current_goals.monthly_topics_goal) and (
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

# --- Tus datos y autorizaciones ------------------------------------------------------------------

status = me.consent_status
with st.container(key="card-data"):
    st.subheader("Tus datos y autorizaciones", anchor=False)
    with st.container(horizontal=True):
        if status.data_processing.granted_at is not None:
            st.badge(
                f"Datos: autorizado el {short_date(status.data_processing.granted_at.date())}",
                color="green",
            )
        if status.pilot_research.granted:
            arm = ARM_LABEL.get(enrollment.pilot_arm or "", "")
            st.badge(f"Piloto: participas · {arm}" if arm else "Piloto: participas", color="blue")
        else:
            st.badge("Piloto: no participas", color="gray")
    st.caption(
        "Puedes salir del piloto sin perder tu ruta ni tu badge, o revocar la autorización y "
        "pedir que borremos tus datos."
    )
    with st.container(horizontal=True, vertical_alignment="center"):
        if st.button("Gestionar mis autorizaciones", key="consents-manage"):
            state.manage_consents = True
        st.page_link(DATA_RIGHTS_PAGE, label="Tus derechos y quién ve cada dato →")


def _close_consents() -> None:
    """Cierra la ventana (también con la «x» o Esc)."""
    state.manage_consents = False


@st.dialog("Gestionar mis autorizaciones", width="medium", on_dismiss=_close_consents)
def _manage_consents() -> None:
    """E11b · Gestionar autorizaciones (ventana modal, V-051)."""
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


if state.manage_consents:
    _manage_consents()
