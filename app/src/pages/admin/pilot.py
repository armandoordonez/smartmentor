"""AD4 · Piloto y AD4b · Vista previa de la ruta fija.

El administrador define las fechas, sortea los grupos (con una semilla fija y reproducible) e inicia
el piloto. Si está listo para iniciar, el sorteo ya se hizo o el piloto ya arrancó lo decide la API
(`GET /pilots/{id}/readiness`, `409 PILOT_ALREADY_STARTED`, `422 PILOT_NOT_READY`).
"""

from collections.abc import Callable

import streamlit as st

from clients.base import ApiError
from clients.models_staff import Pilot, PilotUpdate
from components.layout import render_page_header
from components.staff_theme import PILOT_STATUS_BADGE, READINESS_TEXT
from core.container import get_client
from core.staff_errors import show_staff_error
from core.staff_state import METRICS
from services.staff_admin import plural_learners

client = get_client()

render_page_header(
    "Configuración del piloto",
    breadcrumb="Admin › Piloto",
    caption=(
        "Define la ruta, las fechas y los grupos. Solo los aprendices con consentimiento "
        "informado entran al análisis."
    ),
)

try:
    found = client.find_pilot_id()
    if found is None:
        # Figma no dibuja este estado (F-013 en proyecto/seguimiento/FIGMA.md).
        st.info(
            "Todavía no hay un piloto configurado. Se crea con `POST /pilots` (ruta y fechas); "
            "esta pantalla todavía no tiene el formulario para crearlo."
        )
        st.stop()
    pilot_id: int = found
    pilot: Pilot = client.get_pilot(pilot_id)
    readiness = client.get_pilot_readiness(pilot_id)
except ApiError as error:
    show_staff_error(error)
    st.stop()

locked = pilot.status in ("running", "closed")
label, color = PILOT_STATUS_BADGE[pilot.status]
st.badge(label, color=color)


def _call[T](call: Callable[..., T], *args: object) -> T | None:
    try:
        return call(*args)
    except ApiError as error:
        show_staff_error(error)
        return None


st.subheader("Ruta y fechas", anchor=False)
path_name = pilot.learning_path.name + (
    f" · {pilot.learning_path.group_label}" if pilot.learning_path.group_label else ""
)
st.selectbox("Ruta", [path_name], disabled=True, key="p-path")
start_col, end_col = st.columns(2)
starts = start_col.date_input("Inicio", value=pilot.starts_on, disabled=locked, key="p-start")
ends = end_col.date_input("Fin", value=pilot.ends_on, disabled=locked, key="p-end")
posttest = st.date_input(
    "Post-test diferido (opcional)", value=pilot.delayed_posttest_on, disabled=locked, key="p-post"
)
st.caption("Entre 2 y 4 semanas después del cierre, para medir retención.")

st.subheader("Asignación al azar", anchor=False)
if pilot.groups is None:
    st.caption("Todavía no se sortearon los grupos.")
else:
    personalized_col, fixed_col = st.columns(2)
    personalized_col.markdown(
        f"**Ruta personalizada**  \n{plural_learners(pilot.groups.personalized)}"
    )
    fixed_col.markdown(f"**Ruta fija**  \n{plural_learners(pilot.groups.fixed)}")
seed = st.number_input(
    "Semilla del sorteo", 0, 1_000_000, pilot.random_seed or 2026, disabled=locked, key="p-seed"
)
st.caption(
    f"Semilla del sorteo: {pilot.random_seed if pilot.random_seed is not None else seed} · solo "
    "se puede volver a sortear antes de iniciar."
)
if st.button(
    "Volver a sortear" if pilot.groups else "Sortear grupos", key="p-randomize", disabled=locked
):
    body = PilotUpdate(
        learning_path_id=pilot.learning_path.id,
        starts_on=starts,
        ends_on=ends,
        delayed_posttest_on=posttest,
        random_seed=int(seed),
    )
    if (
        _call(client.update_pilot, pilot_id, body) is not None
        and _call(client.randomize_pilot, pilot_id) is not None
    ):
        st.rerun()
if st.button("Vista previa de la ruta fija (solo lectura)", key="p-preview"):
    st.session_state["p-preview-open"] = True

if st.session_state.get("p-preview-open"):
    try:
        preview = client.get_fixed_path_preview(pilot_id)
    except ApiError as error:
        show_staff_error(error)
    else:
        with st.container(border=True, key="panel-fixed-preview"):
            st.subheader("Vista previa · ruta fija", anchor=False)
            st.badge("Solo lectura", color="gray")
            st.caption(
                "Así ve la ruta un aprendiz del grupo de ruta fija. Es una vista de referencia: "
                "el admin no entra a la cuenta de ningún aprendiz ni puede avanzar o responder "
                "por él."
            )
            for step in preview.steps:
                st.markdown(
                    f"**{step.step_order}** · {step.name} · "
                    "Incluido para todos los aprendices del grupo"
                )
            st.markdown(
                f"Después de los {len(preview.steps)} temas: evaluación final "
                f"({preview.final_pass_threshold} % para el badge)."
            )
            st.caption(
                "Ruta personalizada: cada aprendiz omite los temas que domina en el diagnóstico "
                f"({preview.mastery_skip_threshold} % o más) y suma sus prerrequisitos débiles. "
                "El contenido, los quizzes y los umbrales son los mismos en los dos grupos."
            )
            if st.button("Cerrar", key="p-preview-close"):
                st.session_state["p-preview-open"] = False
                st.rerun()

st.subheader("Consentimiento informado", anchor=False)
pending = pilot.consents.total - pilot.consents.accepted
st.badge(
    f"{pending} pendientes" if pending != 1 else "1 pendiente",
    color="orange" if pending else "green",
)
st.caption(
    f"{pilot.consents.accepted} de {pilot.consents.total} aprendices aceptaron. Solo ellos entran "
    "al análisis (Ley 1581 de 2012)."
)
st.subheader("Ítems equivalentes", anchor=False)
equivalent = pilot.equivalent_items_topics == pilot.topics_total and pilot.topics_total > 0
st.badge("Verificado" if equivalent else "Incompleto", color="green" if equivalent else "orange")
st.caption(
    f"{pilot.equivalent_items_topics} de {pilot.topics_total} temas tienen ítems equivalentes "
    "(versiones paralelas de la evaluación final y la prueba de retención), necesarios para la "
    "ganancia de Hake."
)
st.caption(
    "Sin grupo de ruta fija no se puede calcular la d de Cohen; la ganancia de Hake se reportaría "
    "solo para la ruta personalizada."
)

if not readiness.ready:
    missing = [READINESS_TEXT.get(code, code) for code in readiness.missing]
    st.warning("Aún no se puede iniciar el piloto: " + "; ".join(missing) + ".")

with st.container(horizontal=True):
    if st.button("Guardar borrador", key="p-save", disabled=locked):
        body = PilotUpdate(
            learning_path_id=pilot.learning_path.id,
            starts_on=starts,
            ends_on=ends,
            delayed_posttest_on=posttest,
            random_seed=int(seed),
        )
        if _call(client.update_pilot, pilot_id, body) is not None:
            st.toast("Borrador guardado")
    start_clicked = st.button(
        "Iniciar piloto",
        type="primary",
        key="p-start-btn",
        disabled=locked or not readiness.ready,
    )
    if start_clicked and _call(client.start_pilot, pilot_id) is not None:
        st.rerun()
    if st.button("Ver métricas", key="p-metrics", type="tertiary"):
        st.switch_page(METRICS)
