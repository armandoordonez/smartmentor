"""AD5 · Cursos, rutas e inscripciones.

El administrador ve todos los cursos (`GET /courses?mine=false`), asigna instructor
(`PATCH /courses/{id}/owner`) y gestiona inscripciones: inscribir, retirar y mover de ruta. Los
cursos y las inscripciones no se eliminan, para no perder el historial de intentos; mover o retirar
a un aprendiz lo saca del análisis del piloto (lo aplica la API).
"""

from collections.abc import Callable

import streamlit as st

from clients.base import ApiError
from clients.models_staff import Course
from components.layout import render_notice, render_page_header
from components.staff_theme import (
    ADMIN_ENROLLMENT_BADGE,
    CONSENT_BADGE,
    COURSE_BADGE,
    PILOT_ARM_BADGE,
)
from components.table import Actions, Row, render_table
from core.container import get_client
from core.staff_errors import show_staff_error
from core.staff_state import NEW_COURSE, get_staff_state

client = get_client()
state = get_staff_state()

render_page_header(
    "Cursos, rutas e inscripciones",
    breadcrumb="Admin › Cursos y rutas",
    caption=(
        "Gestiona todos los cursos y rutas del sistema. Los cursos y las inscripciones se "
        "desactivan o se retiran, no se eliminan, para no perder el historial de intentos."
    ),
)

try:
    courses = client.list_courses(mine=False, limit=100).items
    enrollments = client.list_admin_enrollments().items
    users = client.list_users(limit=100).items
except ApiError as error:
    show_staff_error(error)
    st.stop()

with st.container(horizontal=True):
    # Como Figma AD5: «Inscribir aprendiz» es la acción principal (V-023).
    if st.button("Crear curso", key="ce-create"):
        state.course_id = None
        state.job_id = None
        st.session_state.pop("nc-view", None)
        st.session_state.pop("nc-draft", None)
        st.switch_page(NEW_COURSE)
    if st.button("Inscribir aprendiz", type="primary", key="ce-enroll"):
        st.session_state["ce-panel"] = ("enroll", None)

user_names = {u.id: u.full_name for u in users}


def _owner_name(course: Course) -> str | None:
    """El dueño del curso: el de los fixtures o, con la API real, el que indica `owner_user_id`."""
    if course.owner is not None:
        return course.owner.full_name
    if course.owner_user_id is not None:
        return user_names.get(course.owner_user_id, f"Usuario {course.owner_user_id}")
    return None


st.subheader("Cursos y rutas", anchor=False)
course_rows = [
    Row(
        key=str(course.id),
        cells=[
            course.name,
            _owner_name(course) or ":gray[Sin asignar]",
            (
                f"{course.learning_path.group_label or course.learning_path.name} · "
                f"{course.topics_count} temas"
                if course.learning_path
                else ":gray[Sin ruta]"
            ),
            COURSE_BADGE[course.status],
            str(course.enrolled_count),
            Actions(
                (("owner", "Cambiar instructor" if _owner_name(course) else "Asignar instructor"),)
            ),
        ],
    )
    for course in courses
]
clicked = render_table(
    ["Curso", "Instructor", "Ruta", "Estado", "Inscritos", "Acciones"],
    [4, 2, 3, 2, 2, 3],
    course_rows,
    key="admin-courses",
    empty_text="Todavía no hay cursos.",
)
if clicked is not None:
    st.session_state["ce-panel"] = ("owner", int(clicked[0]))

st.subheader("Inscripciones", anchor=False)
enrollment_rows = [
    Row(
        key=str(item.id),
        cells=[
            item.user.full_name,
            f"{item.learning_path.name}"
            + (f" · {item.learning_path.group_label}" if item.learning_path.group_label else ""),
            PILOT_ARM_BADGE[item.pilot_arm] if item.pilot_arm else "—",
            CONSENT_BADGE[item.consent_accepted],
            ADMIN_ENROLLMENT_BADGE[item.status],
            Actions((("move", "Cambiar de ruta"), ("withdraw", "Retirar")))
            if item.status not in ("withdrawn", "completed")
            else None,
        ],
    )
    for item in enrollments
]
clicked_enrollment = render_table(
    ["Aprendiz", "Ruta", "Grupo del piloto", "Consentimiento", "Estado", "Acciones"],
    [3, 3, 2, 2, 2, 3],
    enrollment_rows,
    key="admin-enrollments",
    empty_text="Todavía no hay inscripciones.",
)
if clicked_enrollment is not None:
    st.session_state["ce-panel"] = (clicked_enrollment[1], int(clicked_enrollment[0]))
render_notice(
    "Durante el piloto, cambiar a un aprendiz de ruta o de grupo lo saca del análisis. Quien no "
    "aceptó el consentimiento usa la plataforma, pero sus datos no se analizan."
)

path_options = {c.learning_path.id: c.learning_path.name for c in courses if c.learning_path}
instructors = [u for u in users if "instructor" in u.roles and u.active]
learners = [u for u in users if "learner" in u.roles and u.active]


def _close() -> None:
    st.session_state.pop("ce-panel", None)
    st.rerun()


def _run(call: Callable[..., object], *args: object) -> None:
    try:
        call(*args)
    except ApiError as error:
        show_staff_error(error)
        return
    _close()


panel = st.session_state.get("ce-panel")
if panel is not None:
    kind, target = panel
    with st.container(border=True, key="panel-admin-action"):
        if kind == "owner":
            course = next((c for c in courses if c.id == target), None)
            st.subheader(f"Instructor de «{course.name if course else ''}»", anchor=False)
            ids = [None, *[u.id for u in instructors]]
            names = {u.id: u.full_name for u in instructors}
            owner = st.selectbox(
                "Instructor",
                ids,
                format_func=lambda i: "Sin asignar" if i is None else names[i],
                key="ce-owner",
            )
            confirm = st.button("Guardar instructor", type="primary", key="ce-owner-ok")
            if confirm and course is not None:
                _run(client.set_course_owner, course.id, owner)
        elif kind == "move":
            st.subheader("Cambiar de ruta", anchor=False)
            new_path = st.selectbox(
                "Nueva ruta",
                list(path_options),
                format_func=lambda i: path_options[i],
                key="ce-path",
            )
            if st.button("Mover", type="primary", key="ce-move-ok") and new_path is not None:
                _run(client.move_enrollment, int(target), new_path)
        elif kind == "withdraw":
            st.subheader("Retirar inscripción", anchor=False)
            note = st.text_area("Nota", key="ce-note")
            if st.button("Retirar", type="primary", key="ce-withdraw-ok"):
                _run(client.withdraw_enrollment, int(target), note.strip())
        else:
            st.subheader("Inscribir aprendiz", anchor=False)
            learner_names = {u.id: u.full_name for u in learners}
            learner = st.selectbox(
                "Aprendiz",
                list(learner_names),
                format_func=lambda i: learner_names[i],
                key="ce-learner",
            )
            path = st.selectbox(
                "Ruta",
                list(path_options),
                format_func=lambda i: path_options[i],
                key="ce-enroll-path",
            )
            if (
                st.button("Inscribir", type="primary", key="ce-enroll-ok")
                and learner is not None
                and path is not None
            ):
                _run(client.create_admin_enrollment, learner, path)
        if st.button("Cancelar", key="ce-cancel"):
            _close()
