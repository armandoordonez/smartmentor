"""D1 · Mis cursos.

Lista los cursos del instructor (`GET /courses?mine=true`; la API fuerza `mine` para el
instructor). Cada fila lleva a su syllabus, a su ruta o a la revisión de sus recursos.
"""

import streamlit as st

from clients.base import ApiError
from components.layout import render_notice, render_page_header
from components.staff_theme import COURSE_BADGE
from components.table import Actions, Row, render_table
from core.container import get_client
from core.staff_errors import show_staff_error
from core.staff_state import (
    CONTENT_REVIEW,
    NEW_COURSE,
    PATH_DASHBOARD,
    SYLLABUS_REVIEW,
    get_staff_state,
    pop_flash,
)

client = get_client()
state = get_staff_state()

render_notice(
    "Tu rol: Instructor · Solo ves los cursos que tú creaste. Los de otros instructores no "
    "aparecen."
)
if flash := pop_flash():
    st.success(flash)
render_page_header("Mis cursos")
if st.button("Nuevo curso", type="primary", key="new-course"):
    state.course_id = None
    state.job_id = None
    st.session_state.pop("nc-view", None)
    st.session_state.pop("nc-draft", None)
    st.switch_page(NEW_COURSE)

try:
    courses = client.list_courses(mine=True)
except ApiError as error:
    show_staff_error(error)
    st.stop()

rows = [
    Row(
        key=str(course.id),
        cells=[
            f"**{course.name}**",
            COURSE_BADGE[course.status],
            str(course.topics_count),
            str(course.enrolled_count),
            Actions(
                (("syllabus", "Syllabus"), ("path", "Ruta"), ("resources", "Recursos")),
            ),
        ],
    )
    for course in courses.items
]
clicked = render_table(
    ["Curso", "Estado", "Temas", "Inscritos", "Acciones"],
    [4, 2, 1, 1, 3],
    rows,
    key="courses",
    empty_text="Todavía no tienes cursos. Crea el primero con «Nuevo curso».",
)

if clicked is not None:
    course_id, action = int(clicked[0]), clicked[1]
    course = next(c for c in courses.items if c.id == course_id)
    state.course_id = course.id
    state.path_id = course.learning_path.id if course.learning_path else None
    if action == "syllabus":
        state.job_id = course.extraction_job_id
        st.switch_page(SYLLABUS_REVIEW)
    elif action == "path":
        if state.path_id is None:
            st.warning("Este curso todavía no tiene ruta: revisa y publica sus temas primero.")
        else:
            st.switch_page(PATH_DASHBOARD)
    else:
        st.switch_page(CONTENT_REVIEW)
