"""Video del tema (E6): recuadro con los datos del video y, si hay URL, el reproductor."""

import streamlit as st


def render_video(*, title: str, duration_label: str, url: str | None = None) -> None:
    """Muestra el video de YouTube si hay URL; si no, el recuadro con sus datos (Figma: negro).

    Mide unos 230 px de alto (V-012); el CSS está en `components/video_player.css`.
    """
    if url:
        with st.container(key="video-player"):
            st.video(url)
    # Con reproductor, los datos van en un panel normal; sin él, el recuadro oscuro hace de video.
    with st.container(border=True, key="panel-video-info" if url else "panel-video"):
        st.markdown(f":material/play_circle: **Video recomendado** · {duration_label}")
        st.caption(title)


def render_explanation(text: str, *, source_note: str | None = None) -> None:
    """Explicación del tema en una tarjeta (V-013). El texto viene de la IA: Markdown sin HTML."""
    with st.container(key="card-explanation"):
        st.subheader("Explicación", anchor=False)
        st.markdown(text)
        if source_note:
            st.caption(source_note)
