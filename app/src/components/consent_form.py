"""Consentimiento (A3, A3b, E11b, A3c): las dos casillas y el texto del consentimiento informado.

Los textos legales son de referencia (A3c lo dice: «no es asesoría legal»); la versión final la
revisa la oficina jurídica. La organización responsable y la ventana del piloto vienen por
parámetro (`ORGANIZATION_NAME` y `PILOT_WINDOW_TEXT`), no se escriben aquí.
"""

from dataclasses import dataclass

import streamlit as st

from components.layout import render_page_header


@dataclass(frozen=True)
class ConsentFormResult:
    data_processing: bool
    pilot_research: bool
    read_informed: bool
    """True si se pulsó «Leer el consentimiento informado»."""
    submit: bool


@dataclass(frozen=True)
class InformedConsentResult:
    participate: bool
    back: bool
    proceed: bool
    show_rights: bool


def render_consent_form(
    *,
    key: str,
    data_default: bool = False,
    pilot_default: bool = False,
    submit_label: str = "Continuar",
) -> ConsentFormResult:
    """A3: autorización de datos (obligatoria) y de piloto (opcional)."""
    with st.container(key=f"card-consent-{key}"):
        st.subheader("Tus autorizaciones", anchor=False)
        st.caption("Antes de empezar necesitamos tu autorización para tratar tus datos.")
        data = st.checkbox(
            "Autorizo el tratamiento de mis datos personales para armar mi ruta "
            "(Ley 1581 de 2012). **Obligatorio**",
            value=data_default,
            key=f"{key}-data",
        )
        pilot = st.checkbox(
            "Quiero participar en el piloto de investigación (consentimiento informado). "
            "**Opcional**",
            value=pilot_default,
            key=f"{key}-pilot",
        )
        read = st.button("Leer el consentimiento informado", type="tertiary", key=f"{key}-read")
        submit = st.button(submit_label, type="primary", key=f"{key}-submit", disabled=not data)
    return ConsentFormResult(data, pilot, read, submit)


def render_informed_consent(
    *,
    key: str,
    pilot_window: str,
    participate_default: bool = False,
) -> InformedConsentResult:
    """A3b: consentimiento informado para el piloto, con la decisión de participar o no."""
    render_page_header(
        "Consentimiento informado para el piloto",
        breadcrumb="Crear cuenta › Consentimiento",
        caption=(
            "Lee esto antes de crear tu cuenta. Participar en el piloto es voluntario y no "
            "cambia lo que puedes hacer en la plataforma."
        ),
    )
    left, right = st.columns(2)
    with left:
        _card(
            "Qué es el piloto",
            "SmartMentor es el prototipo de un proyecto de grado de la Maestría en Ciencia de "
            f"Datos. {pilot_window[:1].upper() + pilot_window[1:]} evaluamos si las rutas "
            "personalizadas con IA ayudan a aprender.",
            f"{key}-what",
        )
        _card(
            "Qué datos usamos",
            "Tu hoja de vida y tu descripción de perfil, tus respuestas del diagnóstico, los "
            "quizzes y la evaluación final, tus intentos y tiempos por tema, tus calificaciones "
            "de videos y la encuesta final si decides responderla.",
            f"{key}-data",
        )
        _card(
            "Cómo los protegemos",
            "Se analizan sin tu nombre ni tu correo, solo para este proyecto, según la Ley 1581 "
            "de 2012 de protección de datos personales. Puedes retirar tu consentimiento cuando "
            "quieras desde Mi progreso.",
            f"{key}-protect",
        )
    with right:
        _card(
            "Asignación al azar",
            "Si participas, el sistema te asigna al azar a una ruta personalizada o a una ruta "
            "fija. Las dos tienen el mismo contenido, los mismos umbrales y te permiten obtener "
            "el badge.",
            f"{key}-random",
        )
        _card(
            "Contenido generado con IA",
            "Las explicaciones, las preguntas y la calificación de las respuestas cortas se "
            "generan con IA y las revisa tu instructor. Los quizzes y la evaluación final se "
            "responden sin ayuda de IA.",
            f"{key}-ai",
        )
        with st.container(key="consent-decision"):
            st.markdown("**Tu decisión**")
            choice = st.radio(
                "Tu decisión",
                (
                    "Acepto participar en el piloto y el uso anónimo de mis datos",
                    "Quiero usar la plataforma sin participar en el piloto",
                ),
                index=0 if participate_default else 1,
                label_visibility="collapsed",
                key=f"{key}-decision",
            )
    with st.container(horizontal=True):
        back = st.button("Volver", key=f"{key}-back")
        proceed = st.button("Continuar", type="primary", key=f"{key}-continue")
    rights = st.button("Tus derechos y quién ve cada dato →", type="tertiary", key=f"{key}-rights")
    return InformedConsentResult(
        participate=choice is not None and choice.startswith("Acepto"),
        back=back,
        proceed=proceed,
        show_rights=rights,
    )


def _card(title: str, text: str, key: str) -> None:
    with st.container(key=f"card-{key}"):
        st.markdown(f"**{title}**")
        st.markdown(text)
