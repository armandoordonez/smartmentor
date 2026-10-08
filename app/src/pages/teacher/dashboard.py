"""D3 · Ruta y avance de los estudiantes."""

import streamlit as st

from clients.base import ApiError
from clients.models import PathSettings
from components.formatting import decimal, percent
from components.kpi_cards import render_kpis
from components.layout import render_notice, render_page_header
from components.table import Actions, Row, render_table
from components.theme import ENROLLMENT_BADGE
from core.container import get_services
from core.errors import action_message
from core.navigation import COURSES, STUDENT_DETAIL
from core.session import get_session

services = get_services()
session = get_session()

published = [c for c in services.teacher.courses() if c.status == "published"]
if not published:
    render_page_header("Ruta y avance")
    st.info("Todavía no tienes rutas publicadas. Valida el syllabus de un curso para publicarlo.")
    st.page_link(COURSES, label="Ver mis cursos", icon=":material/arrow_forward:")
    st.stop()

ids = [c.id for c in published]
if session.selected_course_id not in ids:
    session.selected_course_id = ids[0]
dashboard = services.teacher.dashboard(session.selected_course_id)
settings = dashboard.settings


@st.dialog("Editar umbrales")
def edit_settings(current: PathSettings) -> None:
    topic = st.slider(
        "Aprobar un tema con", 50, 100, round(current.topic_threshold * 100), 5, format="%d %%"
    )
    final = st.slider(
        "Aprobar la evaluación final con",
        50,
        100,
        round(current.final_threshold * 100),
        5,
        format="%d %%",
    )
    attempts = st.number_input("Intentos por evaluación", 1, 5, current.max_attempts)
    skip = st.slider(
        "Omitir un tema si el diagnóstico es al menos",
        50,
        100,
        round(current.skip_threshold * 100),
        5,
        format="%d %%",
    )
    st.caption("Los cambios aplican a los próximos intentos, no a los ya presentados.")
    if st.button("Guardar umbrales", type="primary"):
        try:
            services.teacher.update_settings(
                dashboard.course_id,
                PathSettings(
                    topic_threshold=topic / 100,
                    final_threshold=final / 100,
                    max_attempts=int(attempts),
                    skip_threshold=skip / 100,
                ),
            )
        except ApiError as error:
            st.error(action_message(error))
            return
        st.rerun()


render_notice("Tu rol: Docente · Solo ves a los estudiantes inscritos en TUS rutas.")
if len(published) > 1:
    selected = st.selectbox(
        "Ruta",
        ids,
        index=ids.index(dashboard.course_id),
        format_func=lambda i: next(c.title for c in published if c.id == i),
    )
    if selected != dashboard.course_id:
        session.selected_course_id = selected
        st.rerun()

heading, action = st.columns([5, 1], vertical_alignment="center")
with heading:
    render_page_header(
        f"{dashboard.path_title} · Grupo {dashboard.group}",
        caption=(
            f"Ruta publicada · umbrales: tema {percent(settings.topic_threshold)} · final "
            f"{percent(settings.final_threshold)} · {settings.max_attempts} intentos · omitir si "
            f"diagnóstico ≥ {percent(settings.skip_threshold)}"
        ),
    )
with action.container(horizontal=True, horizontal_alignment="right"):
    if st.button("Editar umbrales"):
        edit_settings(settings)

render_kpis(
    [
        (str(dashboard.enrolled), "Inscritos"),
        (percent(dashboard.completion_rate), "Finalización"),
        (str(dashboard.badges_issued), "Badges emitidos"),
        (decimal(dashboard.attempts_per_topic), "Intentos por tema"),
    ]
)

rows = [
    Row(
        key=str(student.user_id),
        cells=[
            student.full_name,
            ENROLLMENT_BADGE[student.enrollment_status],
            f"{student.completed_topics} de {student.total_topics}",
            "Badge emitido" if student.has_badge else student.current_topic or "—",
            percent(student.last_score) if student.last_score is not None else "—",
            Actions((("detail", "Ver detalle"),)),
        ],
    )
    for student in dashboard.students
]
clicked = render_table(
    ["Estudiante", "Inscripción", "Avance", "Tema actual", "Puntaje", ""],
    [2, 1.3, 1, 2, 0.9, 1.2],
    rows,
    key="students",
)
if clicked:
    session.selected_student_id = int(clicked[0])
    st.switch_page(STUDENT_DETAIL)
