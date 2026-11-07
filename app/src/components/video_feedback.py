"""Calificación del video (E6): «¿Te sirvió este video?», etiquetas y comentario anónimo."""

from dataclasses import dataclass

import streamlit as st

from clients.models import VideoRating
from components.theme import VIDEO_RATING_LABEL

_RATINGS: tuple[VideoRating, ...] = ("useful", "audio_issue", "outdated", "too_long")


@dataclass(frozen=True)
class VideoFeedbackResult:
    rating: VideoRating | None
    comment: str | None
    submit: bool


def render_video_feedback(*, key: str) -> VideoFeedbackResult:
    with st.container(key=f"card-{key}"):
        st.markdown("**¿Te sirvió este video?**")
        st.caption("Reportar un problema")
        rating = st.pills(
            "Calificación del video",
            list(_RATINGS),
            format_func=lambda code: VIDEO_RATING_LABEL[code],
            selection_mode="single",
            label_visibility="collapsed",
            key=f"{key}-rating",
        )
        comment = st.text_area(
            "Comentario anónimo (opcional)",
            placeholder="Cuéntale a tu instructor qué mejorarías de este video…",
            max_chars=500,
            key=f"{key}-comment",
        )
        st.caption("Tu instructor ve tu calificación y tu comentario sin tu nombre.")
        submit = st.button("Enviar calificación", key=f"{key}-submit", disabled=rating is None)
    return VideoFeedbackResult(rating, comment.strip() or None, submit)
