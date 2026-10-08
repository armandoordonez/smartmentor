"""Video recomendado y explicación del tema (E6, columna izquierda)."""

import streamlit as st

from clients.models import TopicContent, VideoResource
from components.formatting import percent


def render_video(video: VideoResource | None) -> None:
    if video is not None and video.url:
        st.video(video.url)
        return
    # Sin URL (datos de ejemplo): el recuadro del prototipo con los datos del video.
    with st.container(
        border=True, height=230, horizontal_alignment="center", vertical_alignment="center"
    ):
        if video is None:
            st.caption("Este tema todavía no tiene video recomendado.")
            return
        st.markdown(
            f":material/play_circle: **Video recomendado** · {video.duration_minutes} min · "
            f"Relevancia {percent(video.relevance)}",
            width="content",
        )
        st.caption(video.title, width="content")


def render_explanation(content: TopicContent) -> None:
    with st.container(border=True):
        st.markdown("#### Explicación")
        if content.explanation is None:
            st.caption(
                "Este tema todavía no tiene explicación. En el piloto la genera la capa de IA a "
                "partir de las fuentes del curso y la revisa el docente."
            )
            return
        st.markdown(content.explanation)
        if content.provenance:
            st.caption(content.provenance)
