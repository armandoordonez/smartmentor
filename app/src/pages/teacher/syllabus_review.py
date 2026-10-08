"""D2 · Curso y syllabus: temas extraídos del syllabus, para validar antes de publicar."""

import streamlit as st

from clients.base import ApiError
from clients.models import Topic
from components.layout import render_notice, render_page_header
from components.table import Row, render_table
from components.theme import BLOOM_LABEL, COURSE_BADGE, EMBEDDING_BADGE
from core.container import get_services
from core.errors import action_message
from core.navigation import CONTENT_REVIEW, COURSES, DASHBOARD
from core.session import get_session

services = get_services()
session = get_session()

if session.selected_course_id is None:
    st.info("Elige un curso en «Mis cursos».")
    st.page_link(COURSES, label="Ver mis cursos", icon=":material/arrow_forward:")
    st.stop()

course = services.teacher.course(session.selected_course_id)
topics = services.teacher.topics(course.id)
order_by_id = {t.id: t.order for t in topics}


def prerequisites(topic: Topic) -> str:
    orders = sorted(order_by_id[p] for p in topic.prerequisite_ids if p in order_by_id)
    if not orders:
        return "Ninguno"
    if len(orders) == 1:
        return f"Tema {orders[0]}"
    return "Temas " + ", ".join(map(str, orders[:-1])) + f" y {orders[-1]}"


render_notice(
    "Tu rol: Docente · Validar el syllabus es obligatorio antes de publicar. Los estudiantes no "
    "ven el curso hasta que lo publiques."
)
status_label = COURSE_BADGE[course.status][0].upper()
source = (
    f" · {course.syllabus_file} · {course.syllabus_pages} páginas" if course.syllabus_file else ""
)
heading, actions = st.columns([3, 2], vertical_alignment="center")
with heading:
    render_page_header(course.title, caption=f"{status_label}{source}")
with actions.container(horizontal=True, horizontal_alignment="right"):
    if course.status == "published" and st.button("Ruta y avance"):
        st.switch_page(DASHBOARD)
    if topics and st.button("Revisar contenido"):
        st.switch_page(CONTENT_REVIEW)

if not topics:
    st.info(
        "Este curso todavía no tiene syllabus. Cuando subas el PDF, la capa de IA extraerá los "
        "temas, su nivel de Bloom y sus prerrequisitos para que los valides aquí."
    )
    st.file_uploader(
        "Syllabus en PDF",
        type="pdf",
        disabled=True,
        help="Disponible cuando exista la capa de IA (extracción del syllabus).",
    )
    st.stop()

render_table(
    ["#", "Tema y resultado de aprendizaje", "Bloom", "Prerrequisitos", "Embedding"],
    [0.4, 4, 1.3, 1.6, 1.2],
    [
        Row(
            key=str(topic.id),
            cells=[
                str(topic.order),
                topic.title,
                (BLOOM_LABEL[topic.bloom_level], "blue"),
                prerequisites(topic),
                EMBEDDING_BADGE[topic.embedding_status],
            ],
        )
        for topic in topics
    ],
    key="syllabus",
)

ai_help = "Disponible cuando exista la capa de IA."
with st.container(horizontal=True):
    st.button("Agregar tema", disabled=True, help=ai_help)
    st.button("Editar temas", disabled=True, help=ai_help)
    if course.status == "in_review":
        if st.button("Validar syllabus y publicar", type="primary"):
            try:
                services.teacher.publish(course.id)
            except ApiError as error:
                st.error(action_message(error))
            else:
                st.toast(
                    "Curso publicado: los estudiantes ya ven la ruta.", icon=":material/check:"
                )
                st.rerun()
    elif course.status == "published":
        st.success("Publicado: los estudiantes ya ven esta ruta.")
