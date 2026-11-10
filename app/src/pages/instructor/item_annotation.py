"""D5b · Anotación ciega de preguntas.

Para el instructor asignado como evaluador del curso (`course_evaluators`, DEF-24). La cola no trae
la anotación del otro evaluador (así el kappa de Cohen es válido) y la API rechaza con
`403 EVALUATOR_NOT_ASSIGNED` a quien no está asignado.
"""

import streamlit as st

from clients.base import ApiError
from clients.models_staff import AnnotationBody
from components.annotation_form import AnnotationItemView, render_annotation_form
from components.layout import render_page_header
from components.staff_theme import BLOOM_LABEL
from core.container import get_client
from core.staff_errors import show_staff_error
from core.staff_state import CONTENT_REVIEW, get_staff_state
from services.staff_courses import course_for

client = get_client()
state = get_staff_state()

render_page_header(
    "Anotación de preguntas",
    breadcrumb="Revisión de contenido › Anotación de preguntas",
    caption=(
        "Califica cada pregunta con la rúbrica de 4 criterios, sin ver la nota del otro evaluador."
    ),
)

try:
    course = course_for(client, state.course_id)
    if course is None:
        st.info("Todavía no tienes cursos para anotar.")
        st.stop()
    queue = client.get_annotation_queue(course.id)
except ApiError as error:
    show_staff_error(error)
    st.stop()

if not queue.items:
    st.success("No tienes preguntas pendientes por anotar.")
    st.caption(f"{queue.annotated} de {queue.total} anotadas")
    if st.button("Volver", key="ia-back"):
        st.switch_page(CONTENT_REVIEW)
    st.stop()

item = queue.items[0]
result = render_annotation_form(
    AnnotationItemView(
        item_id=item.item_id,
        stem=item.stem,
        options=tuple(item.options),
        correct_index=item.correct_option,
        meta=f"{item.topic_name} · Bloom: {BLOOM_LABEL[item.bloom_level]}",
    ),
    evaluator_slot=f"Evaluador {item.evaluator_slot} de {item.evaluator_slots_total}",
    progress=f"{queue.annotated} de {queue.total} anotadas",
    key="annotation",
)
if result.close:
    st.switch_page(CONTENT_REVIEW)
if result.save and result.verdict is not None:
    flags = {code: bool(value) for code, value in result.criteria.items()}
    try:
        client.annotate_item(
            item.item_id,
            AnnotationBody(
                single_correct=flags["single_correct"],
                clear_stem=flags["clear_stem"],
                bloom_ok=flags["bloom_ok"],
                plausible_distractors=flags["plausible_distractors"],
                verdict=result.verdict,
                comment=result.comment or None,
            ),
        )
    except ApiError as error:
        show_staff_error(error)
    else:
        st.toast("Anotación guardada")
        st.rerun()
