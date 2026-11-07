"""A3c · Tus datos y tus derechos.

Texto de referencia de la sección de protección de datos (Ley 1581 de 2012). No es asesoría legal:
la versión final la revisa jurídica. La organización responsable sale de `ORGANIZATION_NAME`.
"""

import streamlit as st

from components.layout import render_page_header
from components.table import Row, render_table
from core.config import get_settings
from core.navigation import CONSENT

organization = get_settings().organization_name
responsible = organization[:1].upper() + organization[1:]

render_page_header(
    "Tus datos y tus derechos",
    breadcrumb="Crear cuenta › Consentimiento › Tus datos",
    caption=(
        "Texto de referencia para el prototipo; no es asesoría legal. La versión final debe "
        f"revisarla la oficina jurídica de {organization}."
    ),
)

left, right = st.columns(2)
with left:
    with st.container(key="card-rights-who"):
        st.markdown("**Quién responde**")
        st.markdown(
            f"{responsible} es la responsable del tratamiento de tus datos. El equipo de "
            "SmartMentor los procesa por encargo suyo, solo para tu ruta y para el piloto si "
            "aceptas participar."
        )
    with st.container(key="card-rights-why"):
        st.markdown("**Para qué los usamos**")
        st.markdown(
            "Calcular tu nivel por tema, proponerte una ruta y un objetivo, mostrar tu avance a "
            "ti y a tu instructor, y obtener métricas agregadas del curso."
        )
    with st.container(key="card-rights-rights"):
        st.markdown("**Tus derechos**")
        st.markdown(
            "Conocer, actualizar y rectificar tus datos; pedir prueba de esta autorización; "
            "saber cómo se usan; revocarla o pedir que se borren; consultarlos gratis y "
            "presentar quejas ante la Superintendencia de Industria y Comercio."
        )
        st.markdown(
            "Puedes revocar la autorización o salir del piloto en cualquier momento desde Mi "
            "progreso."
        )
    with st.container(key="card-rights-not"):
        st.markdown("**Lo que no pedimos**")
        st.markdown("Datos sensibles, fecha de nacimiento, dirección ni foto.")
with right:
    st.markdown("**Quién ve cada dato**")
    _ROWS = (
        ("Nombre y correo", "Sí", "Sí", "Sí"),
        ("Hoja de vida", "Sí", "Habilidades", "No"),
        ("Diagnóstico y quizzes", "Sí", "Sí", "Agregados"),
        ("Objetivo de la ruta", "Sí", "Sí", "No"),
        ("Calificaciones y comentarios de videos", "Sí", "Anónimos", "Agregados"),
        ("Datos del piloto", "Sí", "No", "Anónimos"),
    )
    render_table(
        ["Dato", "Tú", "Instructor", "Admin"],
        [3, 1, 1.5, 1.5],
        [Row(str(index), cells) for index, cells in enumerate(_ROWS)],
        key="who-sees",
    )

if st.button("Volver al consentimiento", key="back-to-consent"):
    st.switch_page(CONSENT)
