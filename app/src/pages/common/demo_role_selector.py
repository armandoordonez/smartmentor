"""A1 · Selector de rol. Solo existe con `APP_DATA_SOURCE=fixtures` (sin login ni API).

Con la API real, el rol sale de `GET /me` y el login es de Keycloak (A2, A4 y A5 no se construyen).
Los botones «(Demo del prototipo)» de Figma se reemplazan por *escenarios de datos* (`SCENARIOS`).
"""

import streamlit as st

from clients.fixtures import SCENARIOS, SCENARIOS_BY_KEY, FixturesClient
from clients.models import Role
from components.layout import render_brand
from components.role_card import render_role_card
from core.config import get_settings
from core.labels import glossary
from core.session import get_session

settings = get_settings()
session = get_session()
labels = glossary()

render_brand()
st.title("¿Cómo quieres entrar?", anchor=False, width="content")

_CARDS: tuple[tuple[Role, str, str, str, str], ...] = (
    (
        "learner",
        "Soy aprendiz",
        "Aprende a tu ritmo con una ruta personalizada.",
        (
            "Puede: diagnóstico, temas, quizzes, badge\n"
            "No puede: crear cursos ni ver a otros aprendices"
        ),
        "Entrar como aprendiz",
    ),
    (
        "instructor",
        "Soy instructor",
        "Gestiona cursos, rutas y el avance de tus aprendices.",
        "Puede: syllabus, umbrales, revisar contenido IA\nNo puede: crear usuarios ni ver log LLM",
        "Entrar como instructor",
    ),
    (
        "admin",
        "Soy admin",
        "Administra usuarios, roles y métricas globales.",
        "Puede: todo lo del instructor + usuarios, log LLM\nCuentas creadas solo por otro admin",
        "Entrar como admin",
    ),
)


def _enter(scenario_key: str) -> None:
    scenario = SCENARIOS_BY_KEY[scenario_key]
    client = FixturesClient(scenario_key, directory=settings.app_fixtures_dir)
    session.scenario_key = scenario_key
    session.fixtures_client = client
    session.me = client.get_me()
    session.active_role = scenario.role
    st.rerun()


for column, (role, title, description, permissions, cta) in zip(st.columns(3), _CARDS, strict=True):
    with column:
        if render_role_card(
            role=role,
            badge_label=labels.role_short[role],
            title=title,
            description=description,
            permissions=permissions,
            cta_label=cta,
            key=role,
        ):
            _enter(role)

with st.expander("Escenarios de datos (demostración)"):
    st.caption(
        "Cada escenario carga un estado distinto desde los JSON de `tests/fixtures/`. "
        "Reemplazan a los botones «(Demo del prototipo)» del diseño."
    )
    for scenario in SCENARIOS:
        text_col, button_col = st.columns([4, 1], vertical_alignment="center")
        text_col.markdown(f"**{scenario.label}** · {scenario.description}")
        if button_col.button("Entrar", key=f"scenario-{scenario.key}"):
            _enter(scenario.key)

st.caption(
    "Tus datos solo se tratan con tu autorización expresa, que te pedimos al crear tu cuenta "
    "(Ley 1581 de 2012). El contenido se genera con IA y lo revisa tu instructor."
)
