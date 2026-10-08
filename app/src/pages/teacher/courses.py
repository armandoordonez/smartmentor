"""D1 · Docente · Mis cursos."""

import streamlit as st

from clients.base import ApiError
from components.layout import render_notice, render_page_header
from components.table import Actions, Row, render_table
from components.theme import COURSE_BADGE
from core.container import get_services
from core.errors import action_message
from core.navigation import CONTENT_REVIEW, DASHBOARD, SYLLABUS
from core.session import get_session

services = get_services()
session = get_session()
me = services.teacher.me()
courses = services.teacher.courses()


@st.dialog("Nuevo curso")
def new_course() -> None:
    title = st.text_input("Nombre del curso", placeholder="Ej.: Aprendizaje profundo")
    st.caption(
        "El curso empieza como borrador. Después subes el syllabus en PDF; la IA extrae los temas "
        "y tú los validas antes de publicar."
    )
    if st.button("Crear curso", type="primary"):
        try:
            course = services.teacher.create_course(title)
        except ApiError as error:
            st.error(action_message(error))
            return
        session.selected_course_id = course.id
        st.rerun()


render_notice(
    "Tu rol: Docente · Solo ves los cursos que tú creaste. Los de otros docentes no aparecen."
)
heading, action = st.columns([5, 1], vertical_alignment="center")
with heading:
    render_page_header("Mis cursos", caption=f"Prof. {me.full_name}")
with action.container(horizontal=True, horizontal_alignment="right"):
    if st.button("Nuevo curso", type="primary", icon=":material/add:"):
        new_course()

rows = []
for course in courses:
    actions: list[tuple[str, str]] = [("syllabus", "Syllabus")]
    if course.status == "published":
        actions.append(("path", "Ruta"))
    if course.topic_count:
        actions.append(("resources", "Recursos"))
    rows.append(
        Row(
            key=str(course.id),
            cells=[
                course.title,
                COURSE_BADGE[course.status],
                str(course.topic_count),
                str(course.enrolled_count),
                Actions(tuple(actions)),
            ],
        )
    )

clicked = render_table(
    ["Curso", "Estado", "Temas", "Inscritos", "Acciones"],
    [4, 1.3, 0.8, 0.9, 2.6],
    rows,
    key="courses",
)
if clicked:
    course_id, target = clicked
    session.selected_course_id = int(course_id)
    session.review_topic_id = None
    st.switch_page({"syllabus": SYLLABUS, "path": DASHBOARD, "resources": CONTENT_REVIEW}[target])
