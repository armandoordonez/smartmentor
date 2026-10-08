"""D5 · Revisión de recursos y preguntas generados con IA para un tema."""

import streamlit as st

from clients.base import ApiError
from clients.models import ReviewStatus
from components.formatting import decimal
from components.layout import render_notice, render_page_header
from components.table import Actions, Cell, Row, render_table
from components.theme import BLOOM_LABEL, QUESTION_KIND_LABEL, REVIEW_BADGE
from core.container import get_services
from core.errors import action_message
from core.navigation import COURSES, SYLLABUS
from core.session import get_session

services = get_services()
session = get_session()

if session.selected_course_id is None:
    st.info("Elige un curso en «Mis cursos».")
    st.page_link(COURSES, label="Ver mis cursos", icon=":material/arrow_forward:")
    st.stop()

course = services.teacher.course(session.selected_course_id)
topics = services.teacher.topics(course.id)
if not topics:
    render_page_header("Revisión de contenido generado con IA", caption=course.title)
    st.info("Este curso todavía no tiene temas.")
    st.stop()

topic_ids = [t.id for t in topics]
if session.review_topic_id not in topic_ids:
    session.review_topic_id = topic_ids[0]
topic = next(t for t in topics if t.id == session.review_topic_id)

if st.button("‹ Volver al curso", type="tertiary"):
    st.switch_page(SYLLABUS)
render_notice(
    "Tu rol: Docente · Solo corriges contenido de TUS cursos. Cada corrección actualiza la caché "
    "del tema para todos los estudiantes."
)
render_page_header(
    "Revisión de contenido generado con IA",
    caption=f"{course.title} · Tema {topic.order}: {topic.title}",
)

with st.container(horizontal=True, vertical_alignment="bottom"):
    selected = st.selectbox(
        "Tema",
        topic_ids,
        index=topic_ids.index(topic.id),
        format_func=lambda i: next(f"Tema {t.order}: {t.title}" for t in topics if t.id == i),
        width=420,
    )
    show = st.segmented_control(
        "Mostrar", ["Todo", "Pendientes"], default="Todo", key="review-filter", required=True
    )
if selected != topic.id:
    session.review_topic_id = selected
    st.rerun()

only_pending = show == "Pendientes"
NEXT_ACTIONS: dict[ReviewStatus, tuple[tuple[str, str], ...]] = {
    "pending": (("approved", "Aprobar"), ("retired", "Retirar")),
    "approved": (("retired", "Retirar"),),
    "retired": (("approved", "Restaurar"),),
}
STATUS_BY_ACTION: dict[str, ReviewStatus] = {"approved": "approved", "retired": "retired"}


def change_status(kind: str, item_id: int, status: ReviewStatus) -> None:
    try:
        if kind == "resource":
            services.teacher.set_resource_status(item_id, status)
        else:
            services.teacher.set_question_status(item_id, status)
    except ApiError as error:
        st.error(action_message(error))
        return
    st.toast(f"Quedó como «{REVIEW_BADGE[status][0].lower()}».", icon=":material/check:")
    st.rerun()


resources = [
    r for r in services.teacher.resources(topic.id) if not only_pending or r.status == "pending"
]
resource_rows = [
    Row(
        key=str(r.id),
        cells=[
            r.label,
            r.sources,
            decimal(r.faithfulness, 2) if r.faithfulness is not None else "—",
            REVIEW_BADGE[r.status],
            Actions(NEXT_ACTIONS[r.status]),
        ],
    )
    for r in resources
]
clicked = render_table(
    ["Recurso", "Fuentes", "Fidelidad", "Estado", "Acciones"],
    [3, 2.4, 0.9, 1.1, 1.8],
    resource_rows,
    key="resources",
)
if clicked:
    change_status("resource", int(clicked[0]), STATUS_BY_ACTION[clicked[1]])

st.markdown("#### Banco de preguntas del tema")
questions = [
    q for q in services.teacher.questions(topic.id) if not only_pending or q.status == "pending"
]
question_rows = []
for q in questions:
    cells: list[Cell] = [
        q.prompt,
        BLOOM_LABEL[q.bloom_level],
        QUESTION_KIND_LABEL[q.kind],
        REVIEW_BADGE[q.status],
        Actions(NEXT_ACTIONS[q.status]),
    ]
    question_rows.append(Row(key=str(q.id), cells=cells))
clicked = render_table(
    ["Pregunta", "Bloom", "Tipo", "Estado", "Acciones"],
    [4, 1, 1.3, 1.1, 1.8],
    question_rows,
    key="questions",
)
if clicked:
    change_status("question", int(clicked[0]), STATUS_BY_ACTION[clicked[1]])
