"""D2 · Curso y syllabus, D2b · Editar tema, D2c · Volver a extraer y D2d · Grafo de temas.

El instructor revisa los temas que extrajo la IA, los corrige, valida el grafo y publica. Las
correcciones, los ciclos y el estado del curso los valida la API; la página solo muestra su
respuesta. Las ventanas de Figma (D2b, D2c) son ventanas modales (`st.dialog`).

La sección «Apuntes y lecturas» (R-010) no está en Figma: lista los apuntes del curso, agrega más
con el mismo cargador de D1b (en una ventana) y quita los que sobran. Quitar uno lo saca de las
próximas explicaciones; las ya generadas no cambian.
"""

from typing import Any
from uuid import uuid4

import streamlit as st

from clients.base import ApiError
from clients.models import BloomLevel
from clients.models_staff import Course, CourseTopic, LearningOutcomeWrite, TopicWrite
from components.formatting import file_size
from components.layout import (
    render_notice,
    render_page_header,
    render_page_header_with_actions,
)
from components.material_uploader import (
    MATERIAL_ORIGINS,
    SKIPPABLE_MATERIAL_ERRORS,
    escape_markdown,
    render_material_uploader,
)
from components.staff_theme import BLOOM_COLOR, BLOOM_LABEL, COURSE_BADGE, TOPIC_REVIEW_BADGE
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
from core.widget_state import seed_defaults
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
MAX_MATERIAL_FILES = 5
# Mismo tope que `TopicWrite.estimated_minutes` en la API.
MAX_TOPIC_MINUTES = 100_000
MAX_MATERIAL_BYTES = 10 * 1024 * 1024
MATERIALS_SKIPPED = "sr-materials-skipped"
BLOOM_BY_LABEL: dict[str, BloomLevel] = {label: level for level, label in BLOOM_LABEL.items()}
NEW = -1
PREREQUISITES_PLACEHOLDER = "Elige los temas previos"  # `st.multiselect` trae «Choose options»
SUBTOPIC_SEPARATOR = "·"  # los subtemas van en una línea separados por «·», como en Figma (D2b)

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


def _outcome(outcome_id: int | None, statement: str, bloom: BloomLevel) -> dict[str, Any]:
    """Resultado de aprendizaje en edición; `key` identifica sus campos mientras el panel vive."""
    return {"id": outcome_id, "statement": statement, "bloom": bloom, "key": uuid4().hex[:8]}


def _edit_panel(topic: CourseTopic | None) -> None:
    """D2b · Editar tema (o agregar uno nuevo)."""
    tid = topic.id if topic else NEW
    outcomes_key = f"sr-outcomes-{tid}"
    if outcomes_key not in st.session_state:
        st.session_state[outcomes_key] = [
            _outcome(o.id, o.statement, o.bloom_level)
            for o in (topic.learning_outcomes if topic else [])
        ] or [_outcome(None, "", "apply")]
    outcomes: list[dict[str, Any]] = st.session_state[outcomes_key]
    options = [t.id for t in topics if t.id != tid]
    # Los widgets no llevan `value=`, `index=` ni `default=`: el valor de la API entra por el
    # estado de sesión y no pisa un borrador restaurado al volver de Keycloak (B-040, B-054).
    seed_defaults(
        {
            f"sr-name-{tid}": topic.name if topic else "",
            f"sr-sub-{tid}": f" {SUBTOPIC_SEPARATOR} ".join(topic.subtopics) if topic else "",
            f"sr-bloom-{tid}": BLOOM_LABEL[topic.bloom_level if topic else "apply"],
            f"sr-min-{tid}": topic.estimated_minutes if topic else None,
            f"sr-pre-{tid}": [
                i for i in (topic.prerequisite_topic_ids if topic else []) if i in options
            ],
        }
    )
    for outcome in outcomes:
        seed_defaults(
            {
                f"sr-ob-{tid}-{outcome['key']}": BLOOM_LABEL[outcome["bloom"]],
                f"sr-os-{tid}-{outcome['key']}": outcome["statement"],
            }
        )
    name = st.text_input("Nombre", key=f"sr-name-{tid}")
    subtopics = st.text_input(
        "Subtemas",
        help=f"Sepáralos con «{SUBTOPIC_SEPARATOR}».",
        key=f"sr-sub-{tid}",
    )
    st.markdown("**Resultados de aprendizaje**")
    for index, outcome in enumerate(outcomes):
        # Clave propia de cada resultado, no su posición: al quitar uno, el que ocupa su lugar
        # heredaba el estado del campo y Streamlit ignoraba su valor inicial.
        uid = outcome["key"]
        bloom_col, text_col, remove_col = st.columns([2, 6, 1], vertical_alignment="bottom")
        # La etiqueta se ve una vez, sobre el primer resultado, como en Figma; las demás filas la
        # conservan oculta para que el lector de pantalla la anuncie.
        chosen = bloom_col.selectbox(
            "Verbo de Bloom",
            list(BLOOM_LABEL.values()),
            key=f"sr-ob-{tid}-{uid}",
            label_visibility="visible" if index == 0 else "collapsed",
        )
        outcome["bloom"] = BLOOM_BY_LABEL[chosen]
        outcome["statement"] = text_col.text_input(
            "Resultado", key=f"sr-os-{tid}-{uid}", label_visibility="collapsed"
        )
        if (
            remove_col.button("Quitar", key=f"sr-orm-{tid}-{uid}", type="tertiary")
            and len(outcomes) > 1
        ):
            outcomes.pop(index)
            st.rerun()
    if st.button("+ Agregar resultado de aprendizaje", key=f"sr-oadd-{tid}", type="tertiary"):
        outcomes.append(_outcome(None, "", "apply"))
        st.rerun()
    bloom = st.selectbox("Nivel de Bloom", list(BLOOM_LABEL.values()), key=f"sr-bloom-{tid}")
    # T-057: no está en Figma. Los syllabus casi nunca dicen las horas de cada tema, así que la IA
    # deja el campo vacío; el instructor lo escribe aquí para medir los minutos ahorrados.
    minutes = st.number_input(
        "Minutos estimados (opcional)",
        min_value=1,
        max_value=MAX_TOPIC_MINUTES,
        value=None,
        step=5,
        format="%d",
        placeholder="Sin estimar",
        help="Cuánto tarda un aprendiz en estudiar el tema. Se usa para calcular los minutos "
        "que ahorra quien ya lo domina.",
        key=f"sr-min-{tid}",
    )
    prereqs = st.multiselect(
        "Prerrequisitos",
        options,
        format_func=lambda i: names[i],
        placeholder=PREREQUISITES_PLACEHOLDER,
        key=f"sr-pre-{tid}",
    )
    render_notice("**Si un prerrequisito forma un ciclo, no podrás guardar.**")
    with st.container(horizontal=True):
        delete = bool(topic) and st.button("Eliminar tema", key=f"sr-del-{tid}", type="tertiary")
        st.space("stretch")
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
                subtopics=[
                    part.strip() for part in subtopics.split(SUBTOPIC_SEPARATOR) if part.strip()
                ],
                position=topic.position if topic else len(topics) + 1,
                estimated_minutes=int(minutes) if minutes is not None else None,
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
    st.markdown(
        "La IA procesará de nuevo el syllabus y se perderán tus correcciones: "
        f"{review_summary(counts).replace(' · ', ', ')}. El registro de revisión vuelve a cero."
    )
    with st.container(horizontal=True):
        st.space("stretch")
        if st.button("Cancelar", key="sr-reextract-cancel"):
            st.session_state["sr-reextract"] = False
            st.rerun()
        if st.button("Sí, volver a extraer", type="primary", key="sr-reextract-ok"):
            _go_extract()


def _close_edit() -> None:
    """Cierra la ventana D2b (también con la «x» o Esc) y olvida sus resultados en edición."""
    edit = st.session_state.pop("sr-edit", None)
    st.session_state.pop(f"sr-outcomes-{NEW if edit is None else edit}", None)


def _close_reextract() -> None:
    """Cierra la ventana D2c (también con la «x» o Esc)."""
    st.session_state["sr-reextract"] = False


def _materials_panel() -> None:
    """Ventana «Agregar apuntes» (R-010): el mismo cargador de D1b."""
    files, too_many = render_material_uploader(
        "sr-materials-upload", max_files=MAX_MATERIAL_FILES, max_bytes=MAX_MATERIAL_BYTES
    )
    if too_many:
        st.error(f"Puedes subir hasta {MAX_MATERIAL_FILES} apuntes a la vez. Quita los que sobran.")
    with st.container(horizontal=True):
        st.space("stretch")
        if st.button("Cancelar", key="sr-materials-cancel"):
            st.session_state["sr-materials"] = False
            st.rerun()
        upload = st.button(
            "Subir apuntes",
            type="primary",
            key="sr-materials-save",
            disabled=not files or too_many,
        )
    if not upload:
        return
    skipped: list[str] = []
    try:
        for name, content, origin in files:
            try:
                client.upload_material(course.id, file=(name, content), origin=origin)
            except ApiError as error:
                if error.code not in SKIPPABLE_MATERIAL_ERRORS:
                    raise
                skipped.append(name)
    except ApiError as error:
        show_staff_error(error)
        return
    st.session_state[MATERIALS_SKIPPED] = skipped
    st.session_state["sr-materials"] = False
    st.rerun()


def _close_materials() -> None:
    """Cierra la ventana «Agregar apuntes» (también con la «x» o Esc)."""
    st.session_state["sr-materials"] = False


def _materials_section() -> None:
    """Apuntes y lecturas del curso (R-010): fuentes del RAG además del syllabus."""
    with st.container(border=True, key="card-course-materials"):
        st.subheader("Apuntes y lecturas", anchor=False)
        st.caption(
            "La IA redacta la explicación de cada tema a partir del syllabus y de estos "
            "documentos. Si quitas uno, deja de usarse en las próximas explicaciones; las que ya "
            "se generaron no cambian."
        )
        try:
            materials = client.list_materials(course.id)
        except ApiError as error:
            show_staff_error(error)
            materials = []
        if skipped := st.session_state.pop(MATERIALS_SKIPPED, None):
            names_text = ", ".join(f"«{escape_markdown(n)}»" for n in skipped)
            st.warning(
                f"No pudimos usar estos apuntes: {names_text}. No tienen texto que la IA pueda "
                "leer o no se admiten. Los demás quedaron guardados."
            )
        if not materials:
            st.caption("Todavía no hay apuntes: las explicaciones usan solo el syllabus.")
        for material in materials:
            with st.container(horizontal=True, key=f"material-item-{material.id}"):
                size = f" · {file_size(material.byte_size)}" if material.byte_size else ""
                name = escape_markdown(material.file_name or f"Apunte {material.id}")
                st.markdown(f"{name}{size} · {MATERIAL_ORIGINS[material.origin]}")
                st.space("stretch")
                if st.button("Quitar apunte", key=f"sr-material-rm-{material.id}", type="tertiary"):
                    try:
                        client.deactivate_material(course.id, material.id)
                    except ApiError as error:
                        show_staff_error(error)
                    else:
                        st.rerun()
        if st.button("Agregar apuntes", key="sr-materials-add"):
            st.session_state["sr-materials"] = True
            st.rerun()


def _table_view() -> None:
    render_notice(NOTICE)
    status_text = COURSE_BADGE[course.status][0].upper()
    syllabus = course.syllabus
    detail = [status_text]
    if syllabus and syllabus.filename:
        detail.append(syllabus.filename)
    if syllabus and syllabus.pages:
        detail.append(f"{syllabus.pages} páginas")
    with render_page_header_with_actions(course.name, caption=" · ".join(detail)):
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
                t.name,
                (BLOOM_LABEL[t.bloom_level], BLOOM_COLOR[t.bloom_level]),
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
        placeholder="Elige un tema",
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
    with st.container(border=True, key="card-review-summary"):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.badge(f"{reviewed_count(counts)} de {len(topics)} temas revisados", color="green")
            st.markdown(review_summary(counts))
        text = (
            "La columna Revisión se llena sola con lo que haces y se usa para calcular el F1 de la "
            "extracción."
        )
        if deleted:
            names_text = ", ".join(f"{t.name} (eliminado)" for t in deleted)
            text += f" Los temas eliminados quedan en una lista aparte: {names_text}."
        st.caption(text)
        with st.container(horizontal=True, vertical_alignment="center"):
            if st.button("Agregar tema", key="sr-add-bottom", disabled=not can_review):
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
    _materials_section()
    if st.button("Ver los temas como grafo", key="sr-graph", type="tertiary"):
        st.session_state["sr-mode"] = "graph"
        st.rerun()
    edit = st.session_state.get("sr-edit")
    if edit is not None and can_review:
        target = next((t for t in topics if t.id == edit), None)
        st.dialog(
            "Editar tema" if target else "Agregar tema", width="medium", on_dismiss=_close_edit
        )(_edit_panel)(target)
    if st.session_state.get("sr-reextract"):
        st.dialog("¿Volver a extraer los temas?", width="small", on_dismiss=_close_reextract)(
            _reextract_panel
        )()
    if st.session_state.get("sr-materials"):
        st.dialog("Agregar apuntes", width="medium", on_dismiss=_close_materials)(
            _materials_panel
        )()


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
            TOPIC_REVIEW_BADGE["corrected"],
            TOPIC_REVIEW_BADGE["added"],
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
