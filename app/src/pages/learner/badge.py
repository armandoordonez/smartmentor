"""E10 · Badge: la insignia Open Badges de la ruta completada y su verificación pública.

Descarga la imagen PNG y el JSON (`assertion.json`) y muestra los datos de verificación que sirve
la API sin sesión. El puntaje, los temas y el ahorro salen de la API; la encuesta final se ofrece
mientras `next_action` sea `answer_survey`.
"""

import json

import streamlit as st

from clients.base import ApiError
from clients.models import BadgeSummary
from components.badge_card import render_badge_hero
from components.formatting import duration, percent_points, short_date
from components.layout import eyebrow
from components.stat_tiles import render_stat_tiles
from core.container import get_client
from core.errors import show_action_error
from core.learner_flow import current_enrollment
from core.session import get_session

ACHIEVEMENTS_PAGE = "pages/learner/achievements.py"
SURVEY_PAGE = "pages/learner/final_survey.py"

client = get_client()
state = get_session().learner
enrollment = current_enrollment(client)

try:
    badge: BadgeSummary = client.get_badge(enrollment.id)
    path = client.get_path(enrollment.id)
    history = client.list_attempt_history(enrollment.id, None)
except ApiError as error:
    show_action_error(error)
    st.stop()

best = max((h.score for h in history), default=None)
score_text = percent_points(best) if best is not None else "—"
render_badge_hero(
    "¡Ruta completada!",
    f"Obtuviste {score_text} en la evaluación final de {badge.learning_path_name}.",
)
progress = enrollment.progress
render_stat_tiles(
    [
        (score_text, "Evaluación final"),
        (f"{progress.steps_done} / {progress.steps_total}", "Temas dominados"),
        (duration(path.savings.skipped_minutes), "Ahorrados"),
    ],
    key="badge",
)
st.caption("Formato Open Badges · imagen PNG + archivo JSON descargables")

try:
    image = client.get_badge_image(badge.public_id)
    assertion = client.get_badge_assertion(badge.public_id)
except ApiError as error:
    show_action_error(error)
    st.stop()

with st.container(horizontal=True):
    share = st.button("Compartir", key="badge-share")
    st.download_button(
        "Descargar badge",
        data=image,
        file_name=f"badge-{badge.public_id}.png",
        mime="image/png",
        type="primary",
        key="badge-download",
    )
    st.download_button(
        "Descargar JSON",
        data=json.dumps(assertion.model_dump(by_alias=True), ensure_ascii=False, indent=2),
        file_name=f"badge-{badge.public_id}.json",
        mime="application/json",
        key="badge-download-json",
    )
    if st.button("Ver mis logros", key="badge-achievements"):
        st.switch_page(ACHIEVEMENTS_PAGE)
if share:
    st.caption("Cualquiera puede comprobar tu badge con esta dirección, sin iniciar sesión:")
    st.code(badge.assertion_url, language=None)

if enrollment.next_action.type == "answer_survey":
    with st.container(key="card-survey"):
        st.markdown("**Encuesta final · opcional**")
        st.caption("Ayúdanos a mejorar SmartMentor en unos 3 minutos. No afecta tu badge.")
        if st.button("Responder encuesta", key="badge-survey"):
            state.survey_step = 1
            st.switch_page(SURVEY_PAGE)

with st.expander("Verificación pública"):
    eyebrow("DATOS QUE VERIFICA CUALQUIER PERSONA")
    st.markdown(f"**{assertion.badge.name}**")
    st.caption(assertion.badge.description)
    st.markdown(
        f"Emitido por **{assertion.badge.issuer.name}** el {short_date(badge.issued_at.date())}."
    )
    if assertion.evidence.narrative:
        st.caption(assertion.evidence.narrative)
    st.caption(
        "Tu correo no aparece en el badge: la API publica solo un hash con sal "
        f"({'protegido' if assertion.recipient.hashed else 'en claro'})."
    )
