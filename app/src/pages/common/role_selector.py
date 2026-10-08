"""A1 · Selector de rol. Entrada del prototipo sin login: cada rol usa un usuario de ejemplo."""

import streamlit as st

from clients.models import Role
from clients.sample_seed import DEMO_USER_BY_ROLE
from components.layout import render_brand
from components.role_card import render_role_card
from core.session import start_session

st.space("large")
render_brand()
with st.container(horizontal_alignment="center"):
    st.title("¿Cómo quieres entrar?", anchor=False, width="content")

student, teacher, admin = st.columns(3, gap="medium")
with student:
    enter_student = render_role_card(
        "student",
        title="Soy estudiante",
        description="Aprende a tu ritmo con una ruta personalizada.",
        can="Puede: diagnóstico, temas, quizzes, badge",
        cannot="No puede: crear cursos ni ver a otros estudiantes",
    )
with teacher:
    enter_teacher = render_role_card(
        "teacher",
        title="Soy docente",
        description="Gestiona cursos, rutas y el avance de tus estudiantes.",
        can="Puede: syllabus, umbrales, revisar contenido IA",
        cannot="No puede: crear usuarios ni ver log LLM",
    )
with admin:
    enter_admin = render_role_card(
        "admin",
        title="Soy admin",
        description="Administra usuarios, roles y métricas globales.",
        can="Puede: usuarios, roles, log LLM y métricas",
        cannot="Cuentas creadas solo por otro admin",
    )

with st.container(horizontal_alignment="center"):
    st.caption(
        "Al continuar aceptas el tratamiento de tus datos (Ley 1581 de 2012). El contenido se "
        "genera con IA y lo revisa tu docente.",
        width="content",
    )
    st.caption(
        ":orange[**Prototipo con datos de ejemplo.**] No hay login: cada rol entra con un "
        "usuario de prueba.",
        width="content",
    )

choices: tuple[tuple[Role, bool], ...] = (
    ("student", enter_student),
    ("teacher", enter_teacher),
    ("admin", enter_admin),
)
for role, clicked in choices:
    if clicked:
        start_session(role, DEMO_USER_BY_ROLE[role])
        st.rerun()
