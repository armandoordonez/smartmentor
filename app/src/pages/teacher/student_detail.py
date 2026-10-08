"""D4 · Detalle de un estudiante inscrito en una ruta del docente."""

import csv
import io

import streamlit as st

from clients.models import StudentDetail
from components.formatting import percent, short_date
from components.layout import render_notice, render_page_header
from components.levels import render_levels
from components.table import Row, render_table
from components.theme import ATTEMPT_BADGE, ENROLLMENT_BADGE
from core.container import get_services
from core.navigation import DASHBOARD
from core.session import get_session

services = get_services()
session = get_session()

if session.selected_course_id is None or session.selected_student_id is None:
    st.info("Elige un estudiante en «Ruta y avance».")
    st.page_link(DASHBOARD, label="Ver ruta y avance", icon=":material/arrow_forward:")
    st.stop()

detail = services.teacher.student_detail(session.selected_course_id, session.selected_student_id)


def attempts_csv(detail: StudentDetail) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["tema", "intento", "puntaje", "aprobado", "fecha"])
    for a in detail.attempts:
        writer.writerow([a.topic_title, a.attempt_number, a.score, a.passed, a.taken_on])
    return buffer.getvalue()


if st.button("‹ Volver a la ruta", type="tertiary"):
    st.switch_page(DASHBOARD)
render_notice(
    "Privacidad: ves el perfil y los intentos solo de estudiantes inscritos en TUS rutas."
)
heading, action = st.columns([4, 1], vertical_alignment="center")
with heading:
    render_page_header(
        detail.user.full_name,
        caption=(
            f"{detail.path_title} · Grupo {detail.group} · "
            f"{ENROLLMENT_BADGE[detail.enrollment_status][0]}"
        ),
    )
with action.container(horizontal=True, horizontal_alignment="right"):
    st.download_button(
        "Descargar intentos",
        data=attempts_csv(detail),
        file_name=f"intentos-{detail.user.id}.csv",
        mime="text/csv",
        icon=":material/download:",
        on_click="ignore",
    )

profile, levels = st.columns(2, gap="medium")
with profile, st.container(border=True, height="stretch"):
    st.caption("**PERFIL Y OBJETIVO**")
    st.markdown(detail.profile_description or ":gray[Sin descripción de perfil.]")
    st.markdown(f"**Objetivo:** {detail.personal_objective or 'sin definir'}")
with levels:
    if detail.levels:
        render_levels(detail.levels, title="NIVEL POR TEMA (DIAGNÓSTICO)")
    else:
        st.info("Todavía no presenta el diagnóstico.")

render_table(
    ["Tema", "Intento", "Puntaje", "Resultado", "Fecha"],
    [3, 0.8, 0.9, 1.2, 1.1],
    [
        Row(
            key=f"{i}",
            cells=[
                attempt.topic_title,
                str(attempt.attempt_number),
                percent(attempt.score),
                ATTEMPT_BADGE[attempt.passed],
                short_date(attempt.taken_on),
            ],
        )
        for i, attempt in enumerate(detail.attempts)
    ],
    key="attempts",
)
