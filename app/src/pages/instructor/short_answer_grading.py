"""D5c · Calificación humana de respuestas cortas.

Muestra respuestas anónimas **sin** la nota del LLM; la API la devuelve solo después de guardar la
calificación humana (así el acuerdo QWK es válido). Las solicitudes «Pedir revisión» de los
aprendices van en otra cola porque no son una muestra aleatoria.
"""

import streamlit as st

from clients.base import ApiError
from clients.models_staff import HumanCriterion, HumanGradingBody, HumanGradingResult, SampleType
from components.layout import render_page_header
from core.container import get_client
from core.staff_errors import show_staff_error
from core.staff_state import CONTENT_REVIEW

MET, NOT_MET = "Cumple", "No cumple"

client = get_client()

render_page_header(
    "Calificación humana de respuestas cortas",
    breadcrumb="Revisión de contenido › Respuestas cortas",
    caption=(
        "Muestra aleatoria y anónima. Calificas cada criterio sin ver la nota del LLM; al guardar "
        "se muestra para comparar. Con estas notas se calcula el acuerdo (QWK)."
    ),
)

sample: SampleType = "learner_request" if st.session_state.get("dg-sample") == 1 else "random"
try:
    queue = client.get_grading_queue(sample)
    other = client.get_grading_queue("random" if sample == "learner_request" else "learner_request")
except ApiError as error:
    show_staff_error(error)
    st.stop()

random_queue = other if sample == "learner_request" else queue
requests_queue = queue if sample == "learner_request" else other
options = {
    0: f"Muestra aleatoria · {random_queue.sample_done} de {random_queue.sample_total}",
    1: f"Solicitudes «Pedir revisión» · {requests_queue.learner_requests}",
}
st.segmented_control(
    "Cola",
    list(options),
    format_func=lambda i: options[i],
    default=1 if sample == "learner_request" else 0,
    label_visibility="collapsed",
    key="dg-sample",
)
st.caption(
    "Las solicitudes de los aprendices van en otra pestaña y no entran en la muestra, porque no "
    "son aleatorias."
)

if not queue.items:
    st.success("No hay respuestas pendientes en esta cola.")
    if st.button("Volver", key="dg-back-empty"):
        st.switch_page(CONTENT_REVIEW)
    st.stop()

answer = queue.items[0]
saved: HumanGradingResult | None = st.session_state.get("dg-result")
with st.container(border=True, key="panel-grading"):
    st.markdown(f"**Respuesta #{answer.code} · {answer.topic_name}**")
    st.markdown(answer.prompt)
    st.markdown(f"«{answer.answer}»")
    st.caption("**RÚBRICA**")
    met: list[bool] = []
    for index, criterion in enumerate(answer.criteria):
        choice = st.segmented_control(
            criterion,
            (MET, NOT_MET),
            selection_mode="single",
            default=None,
            disabled=saved is not None,
            key=f"dg-c-{answer.attempt_answer_id}-{index}",
        )
        met.append(choice == MET)
    complete = all(
        st.session_state.get(f"dg-c-{answer.attempt_answer_id}-{i}") is not None
        for i in range(len(answer.criteria))
    )
    total = sum(met)
    st.markdown(f"**Tu nota: {total} de {len(answer.criteria)}**")
    st.caption("**NOTA DEL LLM · SE MUESTRA AL GUARDAR**")
    if saved is None:
        st.caption("Guarda tu calificación para ver la nota del LLM.")
    else:
        st.markdown(f"**{saved.llm_criteria_met} de {saved.llm_criteria_total}**")
        st.markdown(saved.llm_rationale)
        if saved.agrees:
            st.badge("Coincide con tu nota", color="green")
        else:
            st.badge("Difiere de tu nota", color="orange")
        st.caption(f"prompt {saved.prompt_version}")

with st.container(horizontal=True):
    if st.button("Volver", key="dg-back"):
        st.session_state.pop("dg-result", None)
        st.switch_page(CONTENT_REVIEW)
    if saved is None:
        if st.button("Guardar y siguiente", type="primary", key="dg-save", disabled=not complete):
            count = len(answer.criteria) or 1
            body = HumanGradingBody(
                criteria=[
                    HumanCriterion(criterion=c, met=m, points_awarded=1 if m else 0)
                    for c, m in zip(answer.criteria, met, strict=True)
                ],
                score=round(100 * total / count),
                sample_type=sample,
            )
            try:
                st.session_state["dg-result"] = client.grade_answer(answer.attempt_answer_id, body)
            except ApiError as error:
                show_staff_error(error)
            else:
                st.rerun()
    elif st.button("Siguiente", type="primary", key="dg-next"):
        st.session_state.pop("dg-result", None)
        st.rerun()
