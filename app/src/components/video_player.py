"""Video del tema (E6): recuadro con los datos del video y, si hay URL, el reproductor."""

import streamlit as st


def render_video(*, title: str, duration_label: str, url: str | None = None) -> None:
    """Muestra el video de YouTube si hay URL; si no, el recuadro con sus datos (Figma: negro)."""
    if url:
        st.video(url)
    with st.container(border=True, key="panel-video"):
        st.markdown(f":material/play_circle: **Video recomendado** · {duration_label}")
        st.caption(title)


def render_explanation(text: str, *, source_note: str | None = None) -> None:
    """Explicación del tema. El texto viene de la IA: se muestra como Markdown sin HTML."""
    st.subheader("Explicación", anchor=False)
    st.markdown(text)
    if source_note:
        st.caption(source_note)
