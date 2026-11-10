"""D2 · Curso y syllabus, D2b · Editar tema, D2c · Volver a extraer y D2d · Grafo de temas.

El instructor revisa los temas que extrajo la IA, los corrige, valida el grafo y publica. Las
correcciones, los ciclos y el estado del curso los valida la API; la página solo muestra su
respuesta. Las ventanas de Figma (D2b, D2c) se dibujan como paneles bajo la tabla.
"""

from typing import Any

import streamlit as st

from clients.base import ApiError
from clients.models import BloomLevel
from clients.models_staff import Course, CourseTopic, LearningOutcomeWrite, TopicWrite
from components.layout import render_notice, render_page_header
from components.staff_theme import BLOOM_LABEL, COURSE_BADGE, TOPIC_REVIEW_BADGE
from components.table import Row, render_table
from components.theme import BadgeColor
from components.topic_graph import GraphEdge, GraphNode, ReviewState, render_topic_graph
from core.container import get_client
from core.staff_errors import show_staff_error
from core.staff_state import (
    CONTENT_REVIEW,
    COURSES,
    NEW_COURSE,
    forget_key,
    get_staff_state,
    idempotency_key,
)
from services.staff_courses import (
    course_for,
    cycle_text,
    graph_cycle,
    prereq_text,
    review_summary,
    reviewed_count,
)

NOTICE = (
    "Tu rol: Instructor · Validar el syllabus es obligatorio antes de publicar. Los aprendices "
    "no ven el curso hasta que lo publiques."
)
BLOOM_BY_LABEL: dict[str, BloomLevel] = {label: level for level, label in BLOOM_LABEL.items()}
NEW = -1

client = get_client()
state = get_staff_state()


def _load() -> tuple[Course, list[CourseTopic], Any]:
    try:
        course = course_for(client, state.course_id)
        if course is None:
            st.info("Todavía no tienes cursos. Crea el primero desde «Mis cursos».")
            st.stop()
        topics = client.list_course_topics(course.id)
    except ApiError as error:
        show_staff_error(error)
        st.stop()
    state.course_id = course.id
    return course, topics.topics, topics.review_counts


course, all_topics, counts = _load()
if course.status in ("draft", "extracting", "extraction_failed"):
    # Todavía no hay temas que revisar: se vuelve a la carga del syllabus.
    state.job_id = course.extraction_job_id if course.status == "extracting" else None
    st.session_state.pop("nc-view", None)
    st.switch_page(NEW_COURSE)

topics = sorted((t for t in all_topics if t.review_status != "deleted"), key=lambda t: t.position)
deleted = [t for t in all_topics if t.review_status == "deleted"]
positions = {t.id: t.position for t in topics}
names = {t.id: t.name for t in topics}
can_review = course.status == "in_review"


def _go_extract() -> None:
    try:
        accepted = client.start_extraction(
            course.id,
            confirm_discard_review=True,
            idempotency_key=idempotency_key(f"extraction-{course.id}"),
        )
    except ApiError as error:
        show_staff_error(error)
        return
    forget_key(f"extraction-{course.id}")
    state.job_id = accepted.job_id
    st.session_state.pop("nc-view", None)
    st.session_state["sr-reextract"] = False
    st.switch_page(NEW_COURSE)


def _publish() -> None:
    try:
        client.publish_course(course.id, idempotency_key=idempotency_key(f"publish-{course.id}"))
    except ApiError as error:
        if error.code == "PREREQUISITE_CYCLE" and error.extra.get("cycle"):
            st.error(cycle_text(error.extra["cycle"], names))
        else:
            show_staff_error(error)
        return
    forget_key(f"publish-{course.id}")
    state.flash = (
        f"«{course.name}» se está publicando: la IA genera las explicaciones y los quizzes de "
        "cada tema."
    )
    st.switch_page(COURSES)


def _edit_panel(topic: CourseTopic | None) -> None:
    """D2b · Editar tema (o agregar uno nuevo)."""
    tid = topic.id if topic else NEW
    outcomes_key = f"sr-outcomes-{tid}"
    if outcomes_key not in st.session_state:
        st.session_state[outcomes_key] = [
            {"id": o.id, "statement": o.statement, "bloom": o.bloom_level}
            for o in (topic.learning_outcomes if topic else [])
        ] or [{"id": None, "statement": "", "bloom": "apply"}]
    outcomes: list[dict[str, Any]] = st.session_state[outcomes_key]
    with st.container(border=True, key=f"panel-edit-topic-{tid}"):
        st.subheader("Editar tema" if topic else "Agregar tema", anchor=False)
        name = st.text_input("Nombre", value=topic.name if topic else "", key=f"sr-name-{tid}")
        subtopics = st.text_area(
            "Subtemas",
            value="\n".join(topic.subtopics) if topic else "",
            help="Uno por línea.",
            key=f"sr-sub-{tid}",
        )
        st.markdown("**Resultados de aprendizaje**")
        for index, outcome in enumerate(outcomes):
            bloom_col, text_col, remove_col = st.columns([2, 6, 1], vertical_alignment="bottom")
            labels = list(BLOOM_LABEL.values())
            chosen = bloom_col.selectbox(
                "Verbo de Bloom",
                labels,
                index=labels.index(BLOOM_LABEL[outcome["bloom"]]),
                key=f"sr-ob-{tid}-{index}",
            )
            outcome["bloom"] = BLOOM_BY_LABEL[chosen]
            outcome["statement"] = text_col.text_input(
                "Resultado",
                value=outcome["statement"],
                key=f"sr-os-{tid}-{index}",
                label_visibility="collapsed",
            )
            if remove_col.button("Quitar", key=f"sr-orm-{tid}-{index}") and len(outcomes) > 1:
                outcomes.pop(index)
                st.rerun()
        if st.button("+ Agregar resultado de aprendizaje", key=f"sr-oadd-{tid}", type="tertiary"):
            outcomes.append({"id": None, "statement": "", "bloom": "apply"})
            st.rerun()
        labels = list(BLOOM_LABEL.values())
        bloom = st.selectbox(
            "Nivel de Bloom",
            labels,
            index=labels.index(BLOOM_LABEL[topic.bloom_level]) if topic else 2,
            key=f"sr-bloom-{tid}",
        )
        options = [t.id for t in topics if t.id != tid]
        prereqs = st.multiselect(
            "Prerrequisitos",
            options,
            default=[i for i in (topic.prerequisite_topic_ids if topic else []) if i in options],
            format_func=lambda i: names[i],
            key=f"sr-pre-{tid}",
        )
        st.caption("Si un prerrequisito forma un ciclo, no podrás guardar.")
        with st.container(horizontal=True):
            delete = bool(topic) and st.button("Eliminar tema", key=f"sr-del-{tid}")
            cancel = st.button("Cancelar", key=f"sr-cancel-{tid}")
            save = st.button(
                "Guardar cambios",
                type="primary",
                key=f"sr-save-{tid}",
                disabled=not name.strip(),
            )
    if cancel:
        st.session_state.pop("sr-edit", None)
        st.session_state.pop(outcomes_key, None)
        st.rerun()
    try:
        if delete and topic:
            client.deactivate_topic(topic.id)
        elif save:
            body = TopicWrite(
                name=name.strip(),
                description=topic.description if topic else None,
                subtopics=[line.strip() for line in subtopics.splitlines() if line.strip()],
                position=topic.position if topic else len(topics) + 1,
                estimated_minutes=topic.estimated_minutes if topic else None,
                is_mandatory=topic.is_mandatory if topic else False,
                bloom_level=BLOOM_BY_LABEL[bloom],
                learning_outcomes=[
                    LearningOutcomeWrite(
                        id=o["id"], statement=o["statement"], bloom_level=o["bloom"]
                    )
                    for o in outcomes
                    if o["statement"].strip()
                ],
                prerequisite_topic_ids=list(prereqs),
            )
            if topic:
                client.update_topic(topic.id, body)
            else:
                client.create_topic(course.id, body)
        else:
            return
    except ApiError as error:
        if error.code == "PREREQUISITE_CYCLE" and error.extra.get("cycle"):
            st.error(cycle_text(error.extra["cycle"], names))
        else:
            show_staff_error(error)
        return
    st.session_state.pop("sr-edit", None)
    st.session_state.pop(outcomes_key, None)
    st.rerun()


def _reextract_panel() -> None:
    """D2c · Confirmar volver a extraer."""
    with st.container(border=True, key="panel-reextract"):
        st.subheader("¿Volver a extraer los temas?", anchor=False)
        st.markdown(
            "La IA procesará de nuevo el syllabus y se perderán tus correcciones: "
            f"{review_summary(counts).replace(' · ', ', ')}. El registro de revisión vuelve a cero."
        )
        with st.container(horizontal=True):
            if st.button("Cancelar", key="sr-reextract-cancel"):
                st.session_state["sr-reextract"] = False
                st.rerun()
            if st.button("Sí, volver a extraer", type="primary", key="sr-reextract-ok"):
                _go_extract()


def _table_view() -> None:
    render_notice(NOTICE)
    status_text = COURSE_BADGE[course.status][0].upper()
    syllabus = course.syllabus
    detail = [status_text]
    if syllabus and syllabus.filename:
        detail.append(syllabus.filename)
    if syllabus and syllabus.pages:
        detail.append(f"{syllabus.pages} páginas")
    render_page_header(course.name, caption=" · ".join(detail))
    with st.container(horizontal=True):
        if st.button("Volver a extraer temas", key="sr-reextract-top", disabled=not can_review):
            st.session_state["sr-reextract"] = True
            st.rerun()
        if st.button(
            "Aprobar y publicar", type="primary", key="sr-publish", disabled=not can_review
        ):
            _publish()
    rows = [
        Row(
            key=str(t.id),
            cells=[
                str(t.position),
                f"**{t.name}**",
                BLOOM_LABEL[t.bloom_level],
                prereq_text(t, positions),
                TOPIC_REVIEW_BADGE[t.review_status],
            ],
        )
        for t in topics
    ]
    render_table(
        ["#", "Tema y resultado de aprendizaje", "Bloom", "Prerrequisitos", "Revisión"],
        [1, 5, 2, 3, 2],
        rows,
        key="topics",
        empty_text="Todavía no hay temas.",
    )
    selected = st.selectbox(
        "Tema a editar",
        [t.id for t in topics],
        format_func=lambda i: f"{positions[i]} · {names[i]}",
        key="sr-selected",
        disabled=not topics,
    )
    with st.container(horizontal=True):
        if st.button("Editar tema", key="sr-edit-btn", disabled=not topics or not can_review):
            st.session_state["sr-edit"] = selected
            st.rerun()
        if st.button("Agregar tema", key="sr-add-btn", disabled=not can_review):
            st.session_state["sr-edit"] = NEW
            st.rerun()
        if st.button("Revisar recursos y preguntas", key="sr-resources"):
            state.topic_id = selected
            st.switch_page(CONTENT_REVIEW)
    st.markdown(f"**{reviewed_count(counts)} de {len(topics)} temas revisados**")
    st.caption(review_summary(counts))
    text = (
        "La columna Revisión se llena sola con lo que haces y se usa para calcular el F1 de la "
        "extracción."
    )
    if deleted:
        names_text = ", ".join(f"{t.name} (eliminado)" for t in deleted)
        text += f" Los temas eliminados quedan en una lista aparte: {names_text}."
    st.caption(text)
    with st.container(horizontal=True):
        if st.button("Agregar tema", key="sr-add-bottom", type="tertiary", disabled=not can_review):
            st.session_state["sr-edit"] = NEW
            st.rerun()
        if st.button(
            "Volver a extraer temas",
            key="sr-reextract-bottom",
            type="tertiary",
            disabled=not can_review,
        ):
            st.session_state["sr-reextract"] = True
            st.rerun()
        if st.button("Ver los temas como grafo", key="sr-graph", type="tertiary"):
            st.session_state["sr-mode"] = "graph"
            st.rerun()
    edit = st.session_state.get("sr-edit")
    if edit is not None and can_review:
        _edit_panel(next((t for t in topics if t.id == edit), None))
    if st.session_state.get("sr-reextract"):
        _reextract_panel()


def _graph_view() -> None:
    """D2d · Temas en vista de grafo."""
    try:
        graph = client.get_topic_graph(course.id)
    except ApiError as error:
        show_staff_error(error)
        st.stop()
    render_page_header(
        "Grafo de temas",
        breadcrumb=f"Mis cursos › {course.name} › Temas",
        caption=(
            "Cada flecha va de un prerrequisito al tema que lo necesita. Revisa que no falten ni "
            "sobren flechas antes de aprobar: este grafo define el orden de todas las rutas."
        ),
    )
    cycle = graph_cycle(graph)
    by_id = {t.id: t for t in topics}
    nodes = [
        GraphNode(
            topic_id=n.id,
            label=f"{n.position} · {n.name}",
            detail=f"Bloom · {BLOOM_LABEL[by_id[n.id].bloom_level]}" if n.id in by_id else "",
            state=_state(by_id[n.id]) if n.id in by_id else "unchanged",
        )
        for n in graph.nodes
    ]
    edges = [GraphEdge(e.source, e.target) for e in graph.edges]
    render_topic_graph(nodes, edges, validated=cycle is None)
    if cycle:
        st.error(
            f"{cycle_text(cycle, {n.id: n.name for n in graph.nodes})}. "
            "Corrige los prerrequisitos para poder publicar."
        )
    with st.container(horizontal=True):
        legend: tuple[tuple[str, BadgeColor], ...] = (
            ("Corregido", "blue"),
            ("Agregado por ti", "green"),
            ("Sin cambios", "gray"),
        )
        for label, color in legend:
            st.badge(label, color=color)
    with st.container(horizontal=True):
        if st.button("Ver como tabla", key="sr-table"):
            st.session_state["sr-mode"] = "table"
            st.rerun()
        if st.button(
            "Aprobar y publicar",
            type="primary",
            key="sr-publish-graph",
            disabled=not can_review or cycle is not None,
        ):
            _publish()


def _state(topic: CourseTopic) -> ReviewState:
    return (
        "corrected"
        if topic.review_status == "corrected"
        else ("added" if topic.review_status == "added" else "unchanged")
    )


if st.session_state.get("sr-mode") == "graph":
    _graph_view()
else:
    _table_view()
