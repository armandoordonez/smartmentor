"""D5 · Revisión de recursos y preguntas y D5d · Editar recurso de texto.

Lista los recursos (`GET /topics/{id}/resources`) y las preguntas (`GET /topics/{id}/items`) del
tema elegido. Aprobar, retirar, editar y regenerar son llamadas a la API, que decide si la
transición es válida (`409 INVALID_STATE_TRANSITION`) y recalcula la fidelidad al guardar.
"""

from typing import Any

import streamlit as st

from clients.base import ApiError
from clients.models_staff import CourseTopic, ItemPatch, Resource, ReviewItem
from components.formatting import decimal
from components.layout import render_notice, render_page_header
from components.staff_theme import (
    BLOOM_LABEL,
    ITEM_BADGE,
    ITEM_TYPE_LABEL,
    RESOURCE_BADGE,
)
from components.table import Actions, Row, render_table
from core.container import get_client
from core.staff_errors import show_staff_error
from core.staff_state import (
    ITEM_ANNOTATION,
    SHORT_ANSWER_GRADING,
    SYLLABUS_REVIEW,
    TOPIC_VIDEOS,
    forget_key,
    get_staff_state,
    idempotency_key,
    pop_flash,
)
from services.staff_content import (
    edited_content,
    faithfulness_text,
    next_version,
    sources_text,
)
from services.staff_courses import course_for

client = get_client()
state = get_staff_state()

render_notice(
    "Tu rol: Instructor · Solo corriges contenido de TUS cursos. Cada corrección actualiza la "
    "caché del tema para todos los aprendices."
)
if st.button("‹ Volver al curso", type="tertiary", key="cr-back"):
    st.switch_page(SYLLABUS_REVIEW)

try:
    course = course_for(client, state.course_id)
    if course is None:
        st.info("Todavía no tienes cursos para revisar.")
        st.stop()
    state.course_id = course.id
    topics: list[CourseTopic] = sorted(
        (t for t in client.list_course_topics(course.id).topics if t.review_status != "deleted"),
        key=lambda t: t.position,
    )
    if not topics:
        st.info("Este curso todavía no tiene temas.")
        st.stop()
    topic_ids = [t.id for t in topics]
    default = topic_ids.index(state.topic_id) if state.topic_id in topic_ids else 0
    topic_id = st.selectbox(
        "Tema",
        topic_ids,
        index=default,
        format_func=lambda i: next(f"Tema {t.position}: {t.name}" for t in topics if t.id == i),
        key="cr-topic",
    )
    state.topic_id = topic_id
    topic = next(t for t in topics if t.id == topic_id)
    resources = client.list_topic_resources(topic_id)
    items = client.list_topic_items(topic_id)
except ApiError as error:
    show_staff_error(error)
    st.stop()

render_page_header(
    "Revisión de contenido generado con IA",
    caption=f"{course.name} · Tema {topic.position}: {topic.name}",
)
if flash := pop_flash():
    st.success(flash)
# Los dos contadores van juntos bajo el título, como en Figma D5 (V-022).
with st.container(horizontal=True, key="content-counts"):
    st.badge(f"Recursos ({len(resources)})", color="green")
    st.badge(f"Preguntas ({items.total})", color="gray")


def _act(call: Any, *args: Any, **kwargs: Any) -> None:
    """Ejecuta una acción de revisión y vuelve a dibujar; el error se muestra en la página."""
    try:
        call(*args, **kwargs)
    except ApiError as error:
        show_staff_error(error)
        return
    st.rerun()


def _regenerate(resource: Resource) -> None:
    """Pide una versión nueva con IA (un trabajo en segundo plano).

    La clave de idempotencia se olvida tras el éxito: antes se conservaba y una segunda
    regeneración repetía la primera respuesta sin generar nada (B-029).
    """
    operation = f"regen-{resource.id}"
    try:
        client.regenerate_resource(resource.id, idempotency_key=idempotency_key(operation))
    except ApiError as error:
        show_staff_error(error)
        return
    forget_key(operation)
    state.flash = (
        f"Regenerando «{resource.title}» con IA. La versión nueva aparece aquí al terminar; "
        "vuelve a abrir el tema en unos segundos."
    )
    st.rerun()


# --- Recursos ------------------------------------------------------------------------------

resource_rows = []
for resource in resources:
    actions: list[tuple[str, str]] = []
    if resource.review_status == "pending_review":
        actions.append(("approve", "Aprobar"))
    actions.append(
        (
            "replace" if resource.kind == "video" else "edit",
            "Reemplazar" if resource.kind == "video" else "Editar",
        )
    )
    if resource.kind != "video" and resource.review_status == "approved":
        actions.append(("regenerate", "Regenerar"))
    if resource.review_status == "approved":
        actions.append(("retire", "Retirar"))
    resource_rows.append(
        Row(
            key=str(resource.id),
            cells=[
                resource.title,
                sources_text(resource),
                faithfulness_text(resource),
                RESOURCE_BADGE[resource.review_status],
                Actions(tuple(actions)),
            ],
        )
    )
clicked = render_table(
    ["Recurso", "Fuentes", "Fidelidad", "Estado", "Acciones"],
    [4, 3, 1, 2, 3],
    resource_rows,
    key="resources",
    empty_text="Este tema todavía no tiene recursos generados.",
)
if clicked is not None:
    rid, action = int(clicked[0]), clicked[1]
    if action == "approve":
        _act(client.review_resource, rid, "approved")
    elif action == "retire":
        _act(client.review_resource, rid, "retired")
    elif action == "regenerate":
        _regenerate(next(r for r in resources if r.id == rid))
    elif action == "replace":
        st.switch_page(TOPIC_VIDEOS)
    else:
        st.session_state["cr-edit-resource"] = rid
        st.rerun()


def _resource_editor(resource: Resource) -> None:
    """D5d · Editar la explicación del tema."""
    content = resource.content or {}
    sections = content.get("sections", [])
    sources: list[dict[str, Any]] = list(content.get("sources", []))
    rid = resource.id
    # La versión va en las claves: Streamlit conserva el valor de un campo por su clave, así que
    # sin ella una versión regenerada seguía mostrando (y al guardar, reponía) el texto anterior.
    k = f"{rid}-v{resource.version}"
    with st.container(border=True, key=f"panel-edit-resource-{rid}"):
        st.subheader("Editar la explicación del tema", anchor=False)
        prompt = (
            f" · prompt recurso_texto {resource.prompt_version}" if resource.prompt_version else ""
        )
        # Fidelidad y versión en la misma línea, como Figma D5d (V-028).
        with st.container(horizontal=True, vertical_alignment="center"):
            if resource.faithfulness is not None:
                st.badge(f"Fidelidad {decimal(resource.faithfulness, 2)}", color="green")
            st.caption(f"{topic.name} · versión {resource.version}{prompt}")
        edited_sections: list[tuple[str, str]] = []
        for index, section in enumerate(sections):
            heading = st.text_input(
                "Título de la sección",
                value=section["heading"],
                key=f"cr-h-{k}-{index}",
            )
            body = st.text_area(
                "Texto",
                value=section["body"],
                height=180,
                key=f"cr-b-{k}-{index}",
                label_visibility="collapsed",
            )
            edited_sections.append((heading, body))
        summary = st.text_area("Resumen", value=content.get("summary", ""), key=f"cr-s-{k}")
        st.markdown("**Fuentes citadas**")
        kept = [
            source
            for source in sources
            if st.checkbox(
                f"[{source['n']}] {source['title']}", value=True, key=f"cr-src-{k}-{source['n']}"
            )
        ]
        new_title = st.text_input("+ Agregar fuente", key=f"cr-newsrc-{k}")
        new_url = st.text_input("Dirección de la fuente", key=f"cr-newurl-{k}")
        if new_title.strip() and new_url.strip():
            number = max((s["n"] for s in sources), default=0) + 1
            kept.append(
                {
                    "n": number,
                    "source_id": f"instructor-{number}",
                    "title": new_title.strip(),
                    "url": new_url.strip(),
                    "license": None,
                }
            )
        render_notice(
            "Al guardar, tu versión reemplaza la de la caché para todos los aprendices del tema "
            f"y queda como versión {next_version(resource.version)} (editada por instructor). "
            "La fidelidad se recalcula sobre las fuentes citadas."
        )
        with st.container(horizontal=True):
            regenerate = st.button("Regenerar con IA", key=f"cr-regen-{rid}")
            st.space("stretch")
            cancel = st.button("Cancelar", key=f"cr-cancel-{rid}")
            save = st.button("Guardar y aprobar", type="primary", key=f"cr-save-{rid}")
    if cancel:
        st.session_state.pop("cr-edit-resource", None)
        st.rerun()
    if regenerate:
        _regenerate(resource)
    if save:
        body = edited_content(content, sections=edited_sections, summary=summary, sources=kept)
        try:
            client.update_resource_content(rid, body)
            client.review_resource(rid, "approved")
        except ApiError as error:
            show_staff_error(error)
            return
        forget_key(f"regen-{rid}")
        st.session_state.pop("cr-edit-resource", None)
        st.rerun()


editing = st.session_state.get("cr-edit-resource")
if editing is not None:
    target = next((r for r in resources if r.id == editing and r.content), None)
    if target is not None:
        _resource_editor(target)

# --- Preguntas -----------------------------------------------------------------------------

st.subheader("Banco de preguntas del tema", anchor=False)
item_rows = []
for item in items.items:
    item_actions: list[tuple[str, str]] = []
    if item.review_status in ("pending_review", "auto_rejected"):
        item_actions.append(("approve", "Aprobar"))
    item_actions.append(("edit", "Editar"))
    if item.review_status == "approved":
        item_actions.append(("retire", "Retirar"))
    item_rows.append(
        Row(
            key=str(item.id),
            cells=[
                item.stem,
                BLOOM_LABEL[item.bloom_level],
                ITEM_TYPE_LABEL[item.item_type],
                ITEM_BADGE[item.review_status],
                Actions(tuple(item_actions)),
            ],
        )
    )
clicked_item = render_table(
    ["Pregunta", "Bloom", "Tipo", "Estado", "Acciones"],
    [5, 2, 2, 2, 3],
    item_rows,
    key="items",
    empty_text="Este tema todavía no tiene preguntas.",
)
if clicked_item is not None:
    iid, action = int(clicked_item[0]), clicked_item[1]
    if action == "approve":
        _act(client.update_item, iid, ItemPatch(review_status="approved"))
    elif action == "retire":
        _act(client.update_item, iid, ItemPatch(review_status="retired"))
    else:
        st.session_state["cr-edit-item"] = iid
        st.rerun()


def _item_editor(item: ReviewItem) -> None:
    """Edición de una pregunta: una edición la devuelve a «Por revisar» y dispara la revisión IA."""
    iid = item.id
    with st.container(border=True, key=f"panel-edit-item-{iid}"):
        st.subheader("Editar pregunta", anchor=False)
        stem = st.text_area("Enunciado", value=item.stem, key=f"cr-stem-{iid}")
        options_text = st.text_area(
            "Opciones (una por línea)", value="\n".join(item.options), key=f"cr-opts-{iid}"
        )
        options = [line.strip() for line in options_text.splitlines() if line.strip()]
        correct = None
        if item.item_type == "multiple_choice" and options:
            correct = st.selectbox(
                "Respuesta correcta",
                range(len(options)),
                index=min(item.correct_option or 0, len(options) - 1),
                format_func=lambda i: f"{'ABCDEFGH'[i]}. {options[i]}",
                key=f"cr-correct-{iid}",
            )
        st.caption("Al guardar, la pregunta vuelve a «Por revisar» y la IA la revisa de nuevo.")
        with st.container(horizontal=True):
            cancel = st.button("Cancelar", key=f"cr-icancel-{iid}")
            save = st.button("Guardar", type="primary", key=f"cr-isave-{iid}")
    if cancel:
        st.session_state.pop("cr-edit-item", None)
        st.rerun()
    if save:
        patch = ItemPatch(
            stem=stem.strip(),
            options=options if item.item_type == "multiple_choice" else None,
            correct_option=correct,
        )
        try:
            client.update_item(iid, patch)
        except ApiError as error:
            show_staff_error(error)
            return
        st.session_state.pop("cr-edit-item", None)
        st.rerun()


editing_item = st.session_state.get("cr-edit-item")
if editing_item is not None:
    target_item = next((i for i in items.items if i.id == editing_item), None)
    if target_item is not None:
        _item_editor(target_item)

with st.container(horizontal=True):
    if st.button("Anotar preguntas con la rúbrica", type="primary", key="cr-annotate"):
        st.switch_page(ITEM_ANNOTATION)
    if st.button("Calificar respuestas cortas", key="cr-grade"):
        st.switch_page(SHORT_ANSWER_GRADING)
    if st.button("Videos del tema", key="cr-videos"):
        st.switch_page(TOPIC_VIDEOS)
