"""E2 · Perfil, E3 · Diagnóstico y E4 · Resultado del diagnóstico (los tres pasos de la entrada a
una ruta). El paso se deduce de los datos: sin inscripción, perfil; con diagnóstico pendiente,
preguntas; con diagnóstico entregado, resultado y objetivo.
"""

import streamlit as st

from clients.base import ApiError
from clients.models import Diagnostic, Enrollment, LearningPath
from components.formatting import percent
from components.layout import eyebrow, render_page_header
from components.levels import render_levels
from components.quiz_form import render_options
from components.theme import BLOOM_LABEL
from core.container import get_services
from core.errors import action_message
from core.navigation import CATALOG, MY_PATH
from core.session import get_session

services = get_services()
session = get_session()

if session.selected_path_id is None:
    st.info("Primero elige una ruta en el catálogo.")
    st.page_link(CATALOG, label="Ver rutas", icon=":material/arrow_forward:")
    st.stop()

path = services.catalog.get_path(session.selected_path_id)
enrollment = services.enrollment.active_enrollment(path.id)
if enrollment is not None and enrollment.status != "onboarding":
    st.switch_page(MY_PATH)

PROFILE_EXAMPLE = (
    "Ej.: Soy ingeniera industrial y trabajo hace dos años como analista de datos. Uso Excel y "
    "SQL a diario y sé algo de Python (pandas). Nunca he entrenado un modelo de machine learning "
    "y quiero aprender a predecir la demanda de mi empresa."
)


def profile_step(path: LearningPath) -> None:
    render_page_header(
        "Cuéntanos sobre ti",
        breadcrumb=f"Rutas › {path.title}",
        eyebrow_text="PASO 1 DE 3 · PERFIL",
        caption=(
            "Describe tu formación, experiencia e intereses. Es una señal inicial; el diagnóstico "
            "pesa más."
        ),
    )
    profile = st.text_area(
        "Tu perfil",
        placeholder=PROFILE_EXAMPLE,
        height=120,
        label_visibility="collapsed",
        key="profile-text",
    )
    with st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Atrás"):
            st.switch_page(CATALOG)
        if st.button("Continuar al diagnóstico", type="primary"):
            try:
                services.enrollment.enroll(path.id, profile)
            except ApiError as error:
                st.error(action_message(error))
                return
            session.start_onboarding(path.id)
            st.rerun()


def questions_step(path: LearningPath, enrollment: Enrollment, diagnostic: Diagnostic) -> None:
    questions = diagnostic.questions
    if not questions:
        st.info("Esta ruta todavía no tiene diagnóstico. Puedes empezar por el primer tema.")
        if st.button("Ver mi resultado", type="primary"):
            services.enrollment.submit_diagnostic(enrollment.id, {})
            st.rerun()
        return
    topics = {t.id: t for t in services.catalog.list_topics(path.course_id)}
    index = min(session.diagnostic_index, len(questions) - 1)
    question = questions[index]
    answers = session.diagnostic_answers

    eyebrow(f"PASO 2 DE 3 · DIAGNÓSTICO · Pregunta {index + 1} de {len(questions)}")
    st.progress((index + 1) / len(questions))
    st.badge(
        f"Tema · {topics[question.topic_id].title} · Bloom · {BLOOM_LABEL[question.bloom_level]}",
        color="blue",
    )
    st.subheader(question.prompt, anchor=False)
    choice = render_options(question, selected=answers.get(question.id), key="diagnostic")
    if choice is not None:
        answers[question.id] = choice
    st.caption("Este diagnóstico no cuenta para tu nota. Si no sabes, elige «No lo sé».")

    is_last = index == len(questions) - 1
    with st.container(horizontal=True, vertical_alignment="center"):
        dont_know = st.button("No lo sé", type="tertiary")
        st.space("stretch")
        previous = st.button("Anterior", disabled=index == 0)
        following = st.button(
            "Ver mi resultado" if is_last else "Siguiente",
            type="primary",
            disabled=choice is None,
        )

    if dont_know:
        answers[question.id] = None
    if previous:
        session.diagnostic_index = index - 1
        st.rerun()
    if following or dont_know:
        if not is_last:
            session.diagnostic_index = index + 1
            st.rerun()
        try:
            services.enrollment.submit_diagnostic(enrollment.id, answers)
        except ApiError as error:
            st.error(action_message(error))
            return
        st.rerun()


def result_step(enrollment: Enrollment, diagnostic: Diagnostic) -> None:
    weight = diagnostic.diagnostic_weight
    render_page_header(
        "Tu punto de partida",
        eyebrow_text="PASO 3 DE 3 · OBJETIVO",
        caption=(
            f"Nivel por tema: diagnóstico ({percent(weight)}) + perfil ({percent(1 - weight)}). "
            "Los temas dominados se omiten."
        ),
    )
    render_levels(diagnostic.levels)
    proposed = diagnostic.proposed_objective or ""
    if session.editing_objective:
        objective = st.text_area("Tu objetivo", value=proposed, height=100, key="objective-text")
    else:
        objective = proposed
        st.info(f"**OBJETIVO PROPUESTO PARA TI · GENERADO CON IA**\n\n{proposed}")

    with st.container(horizontal=True, horizontal_alignment="right"):
        if not session.editing_objective and st.button("Editar el objetivo"):
            session.editing_objective = True
            st.rerun()
        if st.button("Confirmar y ver mi ruta", type="primary"):
            try:
                services.enrollment.confirm_objective(enrollment.id, objective)
            except ApiError as error:
                st.error(action_message(error))
                return
            session.editing_objective = False
            st.switch_page(MY_PATH)


if enrollment is None:
    profile_step(path)
else:
    diagnostic = services.enrollment.diagnostic(enrollment.id)
    if diagnostic.submitted:
        result_step(enrollment, diagnostic)
    else:
        questions_step(path, enrollment, diagnostic)
