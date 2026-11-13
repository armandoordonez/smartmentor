"""D5e · Video del tema y videos de respaldo.

El instructor ve los candidatos de YouTube ordenados por similitud, marca si cada uno es pertinente
(con eso se calculan Precision@3 y nDCG@3), elige cuál se usa y cura los videos de respaldo. La
relevancia solo la ve el instructor (C-08). Cada cambio es una llamada a la API.
"""

import re
from collections.abc import Callable

import streamlit as st

from clients.base import ApiError
from clients.models_staff import TopicVideos, VideoCandidate
from components.formatting import percent
from components.layout import render_page_header
from core.container import get_client
from core.staff_errors import show_staff_error
from core.staff_state import CONTENT_REVIEW, VIDEO_QUALITY, get_staff_state
from services.staff_content import video_link_markdown, video_minutes, video_thumbnail_markdown
from services.staff_courses import course_for

YOUTUBE_ID = re.compile(r"(?:v=|youtu\.be/|embed/)?([A-Za-z0-9_-]{11})(?:[&?#].*)?$")
RELEVANT, NOT_RELEVANT = "Pertinente", "No pertinente"

client = get_client()
state = get_staff_state()


def _topic_id() -> int | None:
    if state.topic_id is not None:
        return state.topic_id
    course = course_for(client, state.course_id)
    if course is None:
        return None
    topics = [
        t for t in client.list_course_topics(course.id).topics if t.review_status != "deleted"
    ]
    return min(topics, key=lambda t: t.position).id if topics else None


def _act(call: Callable[..., object], *args: object, **kwargs: object) -> None:
    try:
        call(*args, **kwargs)
    except ApiError as error:
        show_staff_error(error)
        return
    st.rerun()


try:
    topic_id = _topic_id()
    if topic_id is None:
        st.info("Elige un tema desde la revisión de contenido.")
        st.stop()
    videos: TopicVideos = client.list_video_candidates(topic_id)
except ApiError as error:
    show_staff_error(error)
    st.stop()

render_page_header(
    "Video del tema",
    breadcrumb=f"Revisión de contenido › {videos.topic_name}",
    caption=(
        "Candidatos de YouTube ordenados por similitud entre su transcripción y el tema, con "
        "filtros de duración e idioma. Marca si cada uno es pertinente: con eso se calculan "
        "Precision@3 y nDCG@3."
    ),
)

candidates = [c for c in videos.candidates if c.status in ("candidate", "in_use")]
backups = [c for c in videos.candidates if c.status == "backup"]
if not candidates:
    st.info("Todavía no hay candidatos de YouTube para este tema.")


def _meta(video: VideoCandidate) -> str:
    language = f"{video.language} con subtítulos" if video.has_subtitles else video.language
    channel = f"{video.channel} · " if video.channel else ""
    return f"{channel}{video_minutes(video.duration_seconds)} · {language}"


def _candidate(rank: int, video: VideoCandidate) -> None:
    with st.container(key=f"video-candidate-{video.id}"):
        rank_col, play_col, body_col, relevant_col, action_col = st.columns(
            [1, 3, 6, 4, 2], vertical_alignment="center"
        )
        rank_col.markdown(f"**{rank}**")
        # La portada de YouTube abre el video para que el instructor lo vea antes de juzgarlo.
        play_col.markdown(
            video_thumbnail_markdown(video.youtube_video_id) or ":material/play_circle:"
        )
        with body_col:
            st.markdown(f"**{video_link_markdown(video.title, video.youtube_video_id)}**")
            st.caption(_meta(video))
            if video.relevance is not None:
                st.caption(f"Relevancia {percent(video.relevance)} · solo la ve el instructor")
        with relevant_col:
            current = (
                None
                if video.is_relevant is None
                else (RELEVANT if video.is_relevant else NOT_RELEVANT)
            )
            choice = st.segmented_control(
                "¿Es pertinente?",
                (RELEVANT, NOT_RELEVANT),
                default=current,
                label_visibility="collapsed",
                key=f"vid-rel-{video.id}",
            )
        with action_col:
            if video.status == "in_use":
                st.badge("En uso", color="green")
            elif st.button("Usar este", key=f"vid-use-{video.id}"):
                _act(client.update_video_candidate, video.id, status="in_use", is_relevant=None)
        applied = st.session_state.get(f"vid-applied-{video.id}", current)
        if choice is not None and choice != applied:
            # Se recuerda lo ya enviado para no repetir la llamada en cada ejecución.
            st.session_state[f"vid-applied-{video.id}"] = choice
            _act(
                client.update_video_candidate,
                video.id,
                status=None,
                is_relevant=choice == RELEVANT,
            )


# Candidatos en una tarjeta; respaldo y «Agregar video» en otra, como Figma D5e (V-029).
if candidates:
    with st.container(key="card-video-candidates"):
        for rank, candidate in enumerate(candidates, start=1):
            _candidate(rank, candidate)

backup_card = st.container(key="card-video-backups")
with backup_card, st.container(horizontal=True, vertical_alignment="center"):
    st.subheader("Videos de respaldo", anchor=False, width="content")
    st.badge("Curados por ti", color="violet")
backup_card.caption(
    "Si ningún candidato sirve o el video deja de estar disponible, los aprendices ven el "
    "primero de esta lista."
)
with backup_card:
    if not backups:
        st.caption("Todavía no hay videos de respaldo.")
    for position, backup in enumerate(backups, start=1):
        text_col, button_col = st.columns([8, 2], vertical_alignment="center")
        link = video_link_markdown(backup.title, backup.youtube_video_id)
        text_col.markdown(f"{position}.  {link} · {video_minutes(backup.duration_seconds)}")
        if button_col.button("Quitar", key=f"vid-del-{backup.id}", type="tertiary"):
            _act(client.update_video_candidate, backup.id, status="rejected", is_relevant=None)

    with st.container(key="add-video"):
        st.markdown("**Agregar video**")
        link = st.text_input("Pega el enlace de YouTube", key="vid-link")
        title = st.text_input("Título (opcional)", key="vid-title")
        match = YOUTUBE_ID.search(link.strip()) if link.strip() else None
        if link.strip() and match is None:
            st.caption("No reconocemos ese enlace de YouTube.")
        if st.button("Agregar", key="vid-add", disabled=match is None) and match:
            video_id = match.group(1)
            try:
                added = client.add_video_candidate(
                    topic_id, video_id, title.strip() or f"Video de YouTube {video_id}"
                )
                client.update_video_candidate(added.id, status="backup", is_relevant=None)
            except ApiError as error:
                show_staff_error(error)
            else:
                st.rerun()

with st.container(horizontal=True):
    if st.button("Volver", key="vid-back"):
        st.switch_page(CONTENT_REVIEW)
    if st.button("Guardar", type="primary", key="vid-save"):
        st.toast("Cambios guardados")
        st.switch_page(CONTENT_REVIEW)
    if st.button("Ver la calidad según los aprendices →", type="tertiary", key="vid-quality"):
        st.switch_page(VIDEO_QUALITY)
