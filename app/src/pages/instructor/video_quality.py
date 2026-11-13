"""D5f · Calidad de los videos según los aprendices (P2).

El índice (0 a 100), el estado y el mínimo de calificaciones salen de la API; antes de ese mínimo
aparece «Midiendo». La API mide si el video fue útil, no una nota de 1 a 5 ni el efecto en el quiz
(F-012 en `proyecto/seguimiento/FIGMA.md`): esas columnas muestran lo que haya.
Para un video «En revisión» el instructor decide qué hacer. El contrato no trae una ruta propia
para esa decisión: se usa `PATCH /video-candidates/{id}` (ver la bitácora F07c).
"""

import streamlit as st

from clients.base import ApiError
from clients.models_staff import VideoFeedbackSummary, VideoQuality, VideoQualityRow
from components.formatting import decimal, percent
from components.layout import render_page_header
from components.staff_theme import QUALITY_BADGE
from components.table import Row, render_table
from components.theme import VIDEO_RATING_LABEL
from core.container import get_client
from core.staff_errors import show_staff_error
from core.staff_state import TOPIC_VIDEOS, get_staff_state
from services.staff_courses import first_path_id

REPLACE = "Reemplazar por el video de respaldo"
KEEP = "Mantener y volver a medir en 30 días"
RETIRE = "Retirar el video del tema"

client = get_client()
state = get_staff_state()

render_page_header(
    "Calidad de los videos según los aprendices",
    breadcrumb="Revisión de contenido › Calidad de los videos",
    caption=(
        "Índice de 0 a 100 según cuántos aprendices marcan el video como útil, ajustado cuando "
        "hay pocas calificaciones; antes del mínimo aparece como «Midiendo». Desde 75 se "
        "recomienda, entre 60 y 74 queda en observación y por debajo de 60 pasa a revisión."
    ),
)

try:
    path_id = state.path_id or first_path_id(client)
    if path_id is None:
        st.info("Todavía no tienes rutas con videos para medir.")
        st.stop()
    quality: VideoQuality = client.get_video_quality(path_id)
except ApiError as error:
    show_staff_error(error)
    st.stop()


# Las etiquetas llegan con su código desde la API y ya traducidas desde los fixtures.
_LABELS: dict[str, str] = {str(code): text for code, text in VIDEO_RATING_LABEL.items()}


def _rating(row: VideoQualityRow) -> str:
    if row.rating_average is not None:
        return f"{decimal(row.rating_average)} · {row.ratings_count} notas"
    if row.useful_rate is not None and row.ratings_count >= row.ratings_needed:
        return f"{percent(row.useful_rate)} útil · {row.ratings_count} notas"
    return f"{row.ratings_count} de {row.ratings_needed} notas"


def _effect(row: VideoQualityRow) -> str:
    if row.quiz_effect_points is None:
        return "—"
    return f"+{round(row.quiz_effect_points)} pts"


rows = [
    Row(
        key=str(row.video_candidate_id),
        cells=[
            row.topic_label,
            "—" if row.index is None else str(row.index),
            _rating(row),
            "—" if row.watched_fully_rate is None else percent(row.watched_fully_rate),
            _effect(row),
            str(row.reports),
            QUALITY_BADGE[row.status],
        ],
    )
    for row in quality.rows
]
render_table(
    [
        "Tema · video",
        "Índice",
        "Calificación",
        "Vista completa",
        "Efecto en el quiz",
        "Reportes",
        "Estado",
    ],
    [5, 1, 2, 2, 2, 1, 2],
    rows,
    key="video-quality",
    empty_text="Todavía no hay calificaciones de videos.",
)

by_candidate: dict[int, VideoFeedbackSummary] = {f.video_candidate_id: f for f in quality.feedback}
flagged = [row for row in quality.rows if row.status == "under_review"]
decision: tuple[int, str] | None = None
for row in flagged:
    code = row.topic_label.split(" · ")[0]
    feedback = by_candidate.get(row.video_candidate_id)
    if feedback is not None:
        st.subheader(f"{code} · Qué dicen los aprendices", anchor=False)
        with st.container(horizontal=True):
            for label in feedback.labels:
                st.badge(f"{_LABELS.get(label.label, label.label)} · {label.count}", color="gray")
        for comment in feedback.comments:
            st.markdown(f"«{comment}»")
        if feedback.comments_total:
            st.caption(
                f"{feedback.comments_total} comentarios anónimos, agrupados con IA por tema. Tú "
                "ves el texto, nunca el nombre de quien lo escribió."
            )
    st.subheader(f"Tu decisión sobre el video de {code}", anchor=False)
    st.caption(
        "Mientras decides, el video deja de recomendarse y los aprendices ven el video de "
        "respaldo del tema."
    )
    choice = st.radio(
        "Decisión",
        (REPLACE, KEEP, RETIRE),
        index=None,
        label_visibility="collapsed",
        key=f"vq-choice-{row.video_candidate_id}",
    )
    if choice:
        decision = (row.video_candidate_id, choice)

with st.container(horizontal=True):
    if st.button("Volver", key="vq-back"):
        st.switch_page(TOPIC_VIDEOS)
    if st.button("Guardar decisión", type="primary", key="vq-save", disabled=decision is None):
        if decision is not None and decision[1] != KEEP:
            try:
                client.update_video_candidate(decision[0], status="rejected", is_relevant=None)
            except ApiError as error:
                show_staff_error(error)
                st.stop()
        st.toast("Decisión guardada")
