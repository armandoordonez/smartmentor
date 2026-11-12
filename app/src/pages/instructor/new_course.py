"""D1b · Nuevo curso, D1c · Extrayendo temas y D1d · Error al leer el syllabus.

Una sola página con tres vistas, guardadas en `st.session_state["nc-view"]`:
`form` (datos del curso y syllabus), `extracting` (sondeo del trabajo `syllabus.structure`) y
`error` (PDF sin texto). Los datos del formulario se conservan en `nc-draft` porque los widgets
que no se dibujan pierden su valor.
"""

from dataclasses import dataclass

import streamlit as st

from clients.base import ApiError
from clients.jobs import is_done
from clients.models_staff import CourseCreate
from components.layout import render_page_header
from components.loading_steps import render_loading_steps
from core.container import get_client
from core.polling import poll_job_or_rerun
from core.staff_errors import show_staff_error
from core.staff_state import (
    COURSES,
    SYLLABUS_REVIEW,
    forget_key,
    get_staff_state,
    idempotency_key,
)
from services.staff_courses import extraction_steps

MAX_BYTES = 10 * 1024 * 1024
MAX_DESCRIPTION_CHARS = 4000  # igual que `description` en la API de cursos
UPLOAD, PASTE = "Subir PDF", "Pegar texto"
BREADCRUMB = "Mis cursos › Nuevo curso"

client = get_client()
state = get_staff_state()


@dataclass
class Draft:
    name: str = ""
    group: str = ""
    description: str = ""
    mode: str = UPLOAD
    text: str = ""
    file_name: str | None = None
    file_size: int = 0


def _draft() -> Draft:
    if "nc-draft" not in st.session_state:
        st.session_state["nc-draft"] = Draft()
    draft: Draft = st.session_state["nc-draft"]
    return draft


def _set_view(view: str) -> None:
    st.session_state["nc-view"] = view


view = st.session_state.get("nc-view", "extracting" if state.job_id else "form")
draft = _draft()


def _submit(file: tuple[str, bytes] | None) -> None:
    """Crea el curso (una vez) y envía el syllabus; pasa a D1c o D1d según la respuesta."""
    try:
        if state.course_id is None:
            course = client.create_course(
                CourseCreate(
                    name=draft.name,
                    description=draft.description or None,
                    learning_path_name=draft.name,
                    group_label=draft.group or None,
                )
            )
            state.course_id = course.id
            state.path_id = course.learning_path.id if course.learning_path else None
        accepted = client.upload_syllabus(
            state.course_id,
            text=draft.text if file is None else None,
            file=file,
            idempotency_key=idempotency_key(f"syllabus-{state.course_id}"),
        )
    except ApiError as error:
        if error.code == "SYLLABUS_NO_TEXT":
            _set_view("error")
            st.rerun()
        show_staff_error(error)
        return
    forget_key(f"syllabus-{state.course_id}")
    state.job_id = accepted.job_id
    _set_view("extracting")
    st.rerun()


def _form() -> None:
    render_page_header(
        "Nuevo curso",
        breadcrumb=BREADCRUMB,
        caption=(
            "Registra el curso y carga su syllabus. Después revisarás los temas que extraiga la "
            "IA antes de publicar la ruta."
        ),
    )
    with st.container(border=True, key="panel-new-course"):
        st.subheader("Datos del curso", anchor=False)
        draft.name = st.text_input("Nombre del curso", value=draft.name, key="nc-name")
        draft.group = st.text_input("Grupo o periodo", value=draft.group, key="nc-group")
        # El límite es el de la API (4000): con uno menor, Streamlit rechaza el pegado completo.
        draft.description = st.text_area(
            "Descripción corta",
            value=draft.description,
            max_chars=MAX_DESCRIPTION_CHARS,
            height=120,
            key="nc-description",
        )
        st.markdown("**Syllabus**")
        draft.mode = (
            st.segmented_control(
                "Syllabus",
                (UPLOAD, PASTE),
                default=draft.mode,
                label_visibility="collapsed",
                key="nc-mode",
            )
            or draft.mode
        )
        upload = None
        if draft.mode == UPLOAD:
            upload = st.file_uploader(
                "Arrastra aquí el PDF del syllabus", type=["pdf"], key="nc-file"
            )
            st.caption("o haz clic para elegir un archivo · PDF o texto, máximo 10 MB")
            if upload is not None:
                draft.file_name, draft.file_size = upload.name, upload.size
                st.markdown(f"{upload.name} · {upload.size // 1024} KB")
                st.badge("Listo", color="green")
        else:
            draft.text = st.text_area(
                "Texto del syllabus", value=draft.text, height=200, key="nc-text"
            )
        st.caption(
            "El syllabus se procesa con IA para extraer temas, prerrequisitos y resultados de "
            "aprendizaje. Tú revisas, corriges y apruebas todo antes de publicar."
        )
    too_big = upload is not None and upload.size > MAX_BYTES
    if too_big:
        st.error("El archivo pesa más de 10 MB. Sube uno más liviano o pega el texto.")
    has_content = (upload is not None and not too_big) or (
        draft.mode == PASTE and bool(draft.text.strip())
    )
    with st.container(horizontal=True):
        if st.button("Cancelar", key="nc-cancel"):
            st.session_state.pop("nc-draft", None)
            st.session_state.pop("nc-view", None)
            state.course_id = None
            st.switch_page(COURSES)
        go = st.button(
            "Extraer temas con IA",
            type="primary",
            key="nc-submit",
            disabled=not (draft.name.strip() and has_content),
        )
    if go:
        file = (upload.name, upload.getvalue()) if upload is not None else None
        _submit(file if draft.mode == UPLOAD else None)


def _extracting() -> bool:
    """Dibuja D1c; devuelve True si el trabajo sigue en curso (hay que seguir sondeando)."""
    if state.job_id is None:
        st.stop()
    job = client.poll_job(state.job_id)
    failed = job.status == "failed"
    st.title("Extrayendo temas del syllabus", anchor=False)
    action = render_loading_steps(
        "Extrayendo temas del syllabus",
        extraction_steps(job),
        "menos de 20 segundos",
        key="extract",
        error_message=(
            "No pudimos extraer los temas. Tu syllabus está guardado: puedes reintentar."
            if failed
            else None
        ),
        back_label="Volver a mis cursos",
    )
    if job.progress_label and not failed:
        st.caption(job.progress_label)
    if is_done(job) and not failed:
        state.job_id = None
        st.session_state.pop("nc-view", None)
        st.session_state.pop("nc-draft", None)
        st.switch_page(SYLLABUS_REVIEW)
    if action == "back":
        state.job_id = None
        st.session_state.pop("nc-view", None)
        st.switch_page(COURSES)
    if action == "retry" and state.course_id is not None:
        try:
            accepted = client.start_extraction(
                state.course_id,
                confirm_discard_review=False,
                idempotency_key=idempotency_key(f"extraction-{state.course_id}"),
            )
        except ApiError as error:
            show_staff_error(error)
            return False
        forget_key(f"extraction-{state.course_id}")
        state.job_id = accepted.job_id
        st.rerun()
    return not is_done(job)


@st.fragment(run_every="2s")
def _poll() -> None:
    """Vuelve a ejecutar la página cada 2 s mientras el trabajo no termina (contrato, sección 1)."""
    if state.job_id is None:
        st.stop()
    job_id = state.job_id
    job = poll_job_or_rerun(lambda: client.poll_job(job_id))
    if job is not None and is_done(job):
        st.rerun()


def _error() -> None:
    render_page_header("No pudimos leer el syllabus", breadcrumb=BREADCRUMB)
    st.markdown(
        "El PDF parece escaneado: no tiene texto seleccionable. Sube otro archivo o pega el "
        "texto del syllabus."
    )
    name = draft.file_name or "syllabus.pdf"
    st.caption(f"{name} · 0 caracteres de texto detectados")
    st.info("Tus datos del curso están guardados. No se perdió nada.")
    with st.container(horizontal=True):
        if st.button("Pegar el texto", type="primary", key="nc-paste"):
            draft.mode = PASTE
            _set_view("form")
            st.rerun()
        if st.button("Subir otro archivo", key="nc-upload"):
            draft.mode = UPLOAD
            _set_view("form")
            st.rerun()


if view == "extracting" and state.job_id:
    if _extracting():
        _poll()
elif view == "error":
    _error()
else:
    _form()
