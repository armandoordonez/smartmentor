"""D3 · Ruta y avance y D3b · Configurar la ruta.

Muestra los indicadores de la ruta, la tabla de aprendices, la matriz de dominio por tema y los
temas críticos (`GET /learning-paths/{id}/dashboard`). Los umbrales y el objetivo por defecto se
editan en un panel (`PATCH /learning-paths/{id}/settings`); si hay un piloto en curso la API pide
confirmar el cambio (`409 PILOT_RUNNING`).
"""

from collections.abc import Callable

import streamlit as st

from clients.base import ApiError
from clients.models_staff import (
    Dashboard,
    DefaultObjective,
    MasteryStatus,
    PathSettings,
    TopicStat,
)
from components.formatting import percent, percent_points
from components.kpi_cards import Kpi, render_kpis
from components.layout import render_notice, render_page_header_with_actions
from components.staff_theme import ADMIN_ENROLLMENT_BADGE, MASTERY_BADGE
from components.table import Actions, Row, render_table
from components.theme import BLOOM_VERBS
from core.container import get_client
from core.staff_errors import show_staff_error
from core.staff_state import LEARNER_DETAIL, get_staff_state
from services.staff_courses import first_path_id
from services.staff_dashboard import (
    critical_text,
    optional_decimal,
    optional_percent,
    settings_caption,
    stat_by_topic,
)

client = get_client()
state = get_staff_state()

render_notice("Tu rol: Instructor · Solo ves a los aprendices inscritos en TUS rutas.")

try:
    path_id = state.path_id or first_path_id(client)
    if path_id is None:
        st.info("Todavía no tienes rutas. Publica un curso para ver el avance de sus aprendices.")
        st.stop()
    dashboard: Dashboard = client.get_dashboard(path_id)
except ApiError as error:
    show_staff_error(error)
    st.stop()
state.path_id = path_id
current_path: int = path_id
settings = dashboard.settings


def _config_panel() -> None:
    """D3b · Configurar la ruta."""
    default = settings.default_objective or DefaultObjective()
    with st.container(border=True, key="panel-path-settings"):
        st.subheader("Configurar la ruta", anchor=False)
        st.caption("**OBJETIVO POR DEFECTO · OPCIONAL**")
        verbs = list(BLOOM_VERBS)
        verb = st.selectbox(
            "Verbo de Bloom",
            verbs,
            index=verbs.index(default.bloom_verb) if default.bloom_verb in verbs else None,
            placeholder="Elegir",
            key="pd-verb",
        )
        content = st.text_input(
            "Contenido",
            value=default.content or "",
            placeholder="Ej.: modelos de clasificación",
            key="pd-content",
        )
        criterion = st.text_input(
            "Criterio medible",
            value=default.criterion or "",
            placeholder="Ej.: con F1 ≥ 0,7 en un caso real",
            key="pd-criterion",
        )
        st.caption(
            "Si lo dejas vacío, la IA propone un objetivo para cada aprendiz a partir de su perfil "
            "y su diagnóstico."
        )
        st.caption("**UMBRALES**")
        topic_pass = st.number_input(
            "Aprobar un tema",
            0,
            100,
            settings.topic_pass_threshold,
            help="Puntaje mínimo en el quiz del tema.",
            key="pd-topic",
        )
        final_pass = st.number_input(
            "Obtener el badge",
            0,
            100,
            settings.final_pass_threshold,
            help="Puntaje mínimo en la evaluación final.",
            key="pd-final",
        )
        attempts = st.number_input(
            "Intentos por evaluación",
            1,
            10,
            settings.max_attempts,
            help="Cada intento trae preguntas nuevas.",
            key="pd-attempts",
        )
        skip = st.number_input(
            "Omitir un tema",
            0,
            100,
            settings.mastery_skip_threshold,
            help="Dominio en el diagnóstico desde el cual el tema se omite.",
            key="pd-skip",
        )
        needs_confirm = dashboard.pilot_running or st.session_state.get("pd-confirm-needed")
        confirmed = True
        if needs_confirm:
            st.warning(
                "Durante el piloto, cambiar los umbrales afecta la comparación de resultados "
                "entre aprendices."
            )
            confirmed = st.checkbox("Entiendo el efecto y quiero guardar el cambio", key="pd-ok")
        with st.container(horizontal=True):
            cancel = st.button("Cancelar", key="pd-cancel")
            save = st.button("Guardar", type="primary", key="pd-save", disabled=not confirmed)
    if cancel:
        st.session_state["pd-open"] = False
        st.rerun()
    if save:
        objective = (
            DefaultObjective(bloom_verb=verb, content=content, criterion=criterion)
            if (verb or content or criterion)
            else None
        )
        body = PathSettings(
            topic_pass_threshold=int(topic_pass),
            final_pass_threshold=int(final_pass),
            mastery_skip_threshold=int(skip),
            max_attempts=int(attempts),
            short_answer_min_ratio=settings.short_answer_min_ratio,
            level_weights=settings.level_weights,
            default_objective=objective,
            confirm_pilot_change=bool(needs_confirm and confirmed),
        )
        try:
            client.update_path_settings(current_path, body)
        except ApiError as error:
            if error.code == "PILOT_RUNNING":
                st.session_state["pd-confirm-needed"] = True
                st.rerun()
            show_staff_error(error)
            return
        st.session_state["pd-open"] = False
        st.session_state.pop("pd-confirm-needed", None)
        st.rerun()


with render_page_header_with_actions(
    dashboard.learning_path.name
    + (f" · {dashboard.learning_path.group_label}" if dashboard.learning_path.group_label else ""),
    caption=settings_caption(dashboard),
):
    if st.button("Configurar ruta", key="pd-configure"):
        st.session_state["pd-open"] = True
if st.session_state.get("pd-open"):
    _config_panel()

kpis = dashboard.kpis
render_kpis(
    [
        Kpi("enrolled", "Inscritos", str(kpis.enrolled)),
        Kpi("completion", "Finalización", percent(kpis.completion_rate)),
        Kpi("badges", "Badges emitidos", str(kpis.badges_issued)),
        Kpi("attempts", "Intentos por tema", optional_decimal(kpis.attempts_per_topic)),
    ]
)

rows = [
    Row(
        key=str(learner.enrollment_id),
        cells=[
            learner.full_name,
            ADMIN_ENROLLMENT_BADGE[learner.status],
            f"{learner.steps_done} de {learner.steps_total}",
            "Badge emitido" if learner.badge_issued else (learner.current_topic or "—"),
            "—" if learner.current_score is None else percent_points(learner.current_score),
            Actions((("detail", "Ver detalle"),)),
        ],
    )
    for learner in dashboard.learners
]
clicked = render_table(
    ["Aprendiz", "Inscripción", "Avance", "Tema actual", "Puntaje", ""],
    [3, 2, 2, 3, 1, 2],
    rows,
    key="learners",
    empty_text="Todavía no hay aprendices inscritos en esta ruta.",
)
if clicked is not None:
    state.enrollment_id = int(clicked[0])
    st.switch_page(LEARNER_DETAIL)

st.subheader("Dominio del grupo", anchor=False)
st.caption("Haz clic en un aprendiz para ver su detalle")
with st.container(horizontal=True):
    legend: tuple[MasteryStatus, ...] = (
        "passed",
        "in_progress",
        "reinforce",
        "attempts_exhausted",
        "skipped",
        "pending",
    )
    for status in legend:
        label, color = MASTERY_BADGE[status]
        st.badge(label, color=color)

topics = sorted(dashboard.topics, key=lambda t: t.position)
headers = ["Aprendiz", *[f"{t.position} · {t.name}" for t in topics]]
widths = [3, *[2] * len(topics)]
mastery_rows = [
    Row(
        key=str(row.enrollment_id),
        cells=[Actions((("detail", row.full_name),)), *[MASTERY_BADGE[cell] for cell in row.cells]],
    )
    for row in dashboard.mastery
]
stats = stat_by_topic(dashboard)
summary: list[tuple[str, str, Callable[[TopicStat], str]]] = [
    ("first", "Aprobación al 1.er intento", lambda s: optional_percent(s.first_attempt_pass_rate)),
    ("avg", "Intentos promedio", lambda s: optional_decimal(s.avg_attempts)),
    ("drop", "Abandonos", lambda s: str(s.abandonments)),
]
critical_ids = set(dashboard.critical_topic_ids)


def _stat_cell(topic_id: int, fmt: Callable[[TopicStat], str]) -> str:
    """El valor del tema; en rojo si la API lo marcó como crítico (como Figma D3)."""
    if topic_id not in stats:
        return "—"
    value = fmt(stats[topic_id])
    return f":red[{value}]" if topic_id in critical_ids and value != "—" else value


for key, label, fmt in summary:
    mastery_rows.append(
        Row(
            key=f"stat-{key}",
            cells=[f":gray[{label}]", *[_stat_cell(t.topic_id, fmt) for t in topics]],
        )
    )
clicked_row = render_table(
    headers, widths, mastery_rows, key="mastery", empty_text="Sin datos de dominio todavía."
)
if clicked_row is not None and not clicked_row[0].startswith("stat-"):
    state.enrollment_id = int(clicked_row[0])
    st.switch_page(LEARNER_DETAIL)

critical = [t for t in topics if t.topic_id in critical_ids and t.topic_id in stats]
if critical:
    # Figma D3: aviso ámbar con el título en negrita y una línea por tema.
    lines = [critical_text(topic.name, stats[topic.topic_id]) for topic in critical]
    st.warning("\n\n".join(["**Temas críticos**", *lines]))
else:
    st.subheader("Temas críticos", anchor=False)
    st.caption("Todavía no hay temas críticos.")
