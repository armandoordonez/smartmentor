"""D1b · Nuevo curso, D1c · Extrayendo temas y D1d · Error al leer el syllabus.

Una sola página con tres vistas, guardadas en `st.session_state["nc-view"]`:
`form` (datos del curso, syllabus y apuntes), `extracting` (sondeo del trabajo
`syllabus.structure`) y `error` (PDF sin texto). Los datos del formulario se conservan en
`nc-draft` porque los widgets que no se dibujan pierden su valor.

La tarjeta «Apuntes y lecturas» (R-004) no está en Figma: es opcional y no bloquea «Extraer temas
con IA». Los apuntes se suben antes que el syllabus; un apunte sin texto se omite y se avisa en
D1c, y si la extracción falla en D1d, al reintentar la API no los duplica.
"""

from dataclasses import dataclass

import streamlit as st

from clients.base import ApiError
from clients.jobs import is_done
from clients.models_staff import CourseCreate
from components.formatting import file_size
from components.layout import render_page_header
from components.loading_steps import render_loading_steps
from components.material_uploader import (
    SKIPPABLE_MATERIAL_ERRORS,
    MaterialFile,
    escape_markdown,
    render_material_uploader,
)
from core.container import get_client
from core.polling import enter_wait_mode, leave_wait_mode, poll_job_or_rerun
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
# R-004: apuntes por carga (la API admite hasta 20 activos por curso).
MAX_MATERIAL_FILES = 5
SKIPPED_KEY = "nc-material-skipped"
# Figma promete «menos de 20 segundos», pero la extracción con el LLM real tardó más (39 s en el
# recorrido de staff, B-057): se dice un tope honesto, como en las pantallas de carga del aprendiz.
EXTRACTION_ESTIMATE = "hasta 2 minutos"

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


def _upload_materials(course_id: int, materials: list[MaterialFile]) -> None:
    """Sube los apuntes; los que la API rechaza por su contenido se anotan para avisar en D1c."""
    skipped: list[str] = []
    for name, content, origin in materials:
        try:
            client.upload_material(course_id, file=(name, content), origin=origin)
        except ApiError as error:
            if error.code not in SKIPPABLE_MATERIAL_ERRORS:
                raise
            skipped.append(name)
    st.session_state[SKIPPED_KEY] = skipped


def _submit(file: tuple[str, bytes] | None, materials: list[MaterialFile]) -> None:
    """Crea el curso (una vez), sube los apuntes y envía el syllabus; pasa a D1c o D1d."""
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
        if materials:
            _upload_materials(state.course_id, materials)
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
    data_card, syllabus_card = st.columns(2)
    with data_card.container(key="card-new-course-data"):
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
    upload = None
    with syllabus_card.container(key="card-new-course-syllabus"):
        st.subheader("Syllabus", anchor=False)
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
        if draft.mode == UPLOAD:
            upload = st.file_uploader(
                "Arrastra aquí el PDF del syllabus", type=["pdf"], key="nc-file"
            )
            st.caption("o haz clic para elegir un archivo · PDF o texto, máximo 10 MB")
            if upload is not None:
                draft.file_name, draft.file_size = upload.name, upload.size
                with st.container(horizontal=True, key="new-course-file-row"):
                    st.markdown(f"{upload.name} · {file_size(upload.size)}")
                    st.space("stretch")
                    st.badge("Listo", color="green")
        else:
            draft.text = st.text_area(
                "Texto del syllabus", value=draft.text, height=200, key="nc-text"
            )
    materials, too_many = _materials_card()
    st.info(
        "El syllabus se procesa con IA para extraer temas, prerrequisitos y resultados de "
        "aprendizaje. Los apuntes se usan después, al generar la explicación de cada tema. Tú "
        "revisas, corriges y apruebas todo antes de publicar."
    )
    too_big = upload is not None and upload.size > MAX_BYTES
    if too_big:
        st.error("El archivo pesa más de 10 MB. Sube uno más liviano o pega el texto.")
    if too_many:
        st.error(f"Puedes subir hasta {MAX_MATERIAL_FILES} apuntes a la vez. Quita los que sobran.")
    has_content = (upload is not None and not too_big) or (
        draft.mode == PASTE and bool(draft.text.strip())
    )
    with st.container(horizontal=True):
        if st.button("Cancelar", key="nc-cancel"):
            st.session_state.pop("nc-draft", None)
            st.session_state.pop("nc-view", None)
            st.session_state.pop(SKIPPED_KEY, None)
            state.course_id = None
            st.switch_page(COURSES)
        go = st.button(
            "Extraer temas con IA",
            type="primary",
            key="nc-submit",
            disabled=not (draft.name.strip() and has_content) or too_many,
        )
    if go:
        file = (upload.name, upload.getvalue()) if upload is not None else None
        _submit(file if draft.mode == UPLOAD else None, materials)


def _materials_card() -> tuple[list[MaterialFile], bool]:
    """Tarjeta «Apuntes y lecturas · opcional» (R-004): archivos que se enviarán y si sobran."""
    with st.container(key="card-new-course-materials"):
        st.subheader("Apuntes y lecturas · opcional", anchor=False)
        st.caption(
            "La IA redacta la explicación de cada tema a partir de estos documentos. Sin apuntes, "
            "usa solo el syllabus y las explicaciones quedan más cortas."
        )
        return render_material_uploader(
            "nc-materials", max_files=MAX_MATERIAL_FILES, max_bytes=MAX_BYTES
        )


def _retry_text(progress_label: str) -> str:
    """Aviso de reintento de D1c; el prefijo solo va si el trabajo informa un reintento."""
    if progress_label.startswith("Reintentando"):
        return f"La respuesta no tenía el formato esperado · {progress_label}"
    return progress_label


def _extracting() -> bool:
    """Dibuja D1c; devuelve True si el trabajo sigue en curso (hay que seguir sondeando)."""
    if state.job_id is None:
        st.stop()
    # Modo espera: la tarjeta de carga ya está en pantalla; el sondeo no dibuja «Cargando…».
    enter_wait_mode(state.job_id)
    job = client.poll_job(state.job_id)
    failed = job.status == "failed"
    if failed:
        leave_wait_mode()  # con el error en pantalla, reintentar o volver sí muestran el spinner
    with st.container(key="new-course-loading"):
        action = render_loading_steps(
            "Extrayendo temas del syllabus",
            extraction_steps(job),
            EXTRACTION_ESTIMATE,
            key="extract",
            error_message=(
                "No pudimos extraer los temas. Tu syllabus está guardado: puedes reintentar."
                if failed
                else None
            ),
            back_label="Volver a mis cursos",
        )
        if job.progress_label and not failed:
            with st.container(key="new-course-retry"):
                st.markdown(_retry_text(job.progress_label))
        if skipped := st.session_state.get(SKIPPED_KEY):
            names = ", ".join(f"«{escape_markdown(name)}»" for name in skipped)
            st.warning(
                f"No pudimos usar estos apuntes: {names}. No tienen texto que la IA pueda leer "
                "o no se admiten. Los demás quedaron guardados."
            )
    if is_done(job) and not failed:
        leave_wait_mode()
        state.job_id = None
        st.session_state.pop("nc-view", None)
        st.session_state.pop("nc-draft", None)
        st.session_state.pop(SKIPPED_KEY, None)
        st.switch_page(SYLLABUS_REVIEW)
    if action == "back":
        leave_wait_mode()
        state.job_id = None
        st.session_state.pop("nc-view", None)
        st.session_state.pop("nc-draft", None)
        st.session_state.pop(SKIPPED_KEY, None)
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
    st.caption(
        "El PDF parece escaneado: no tiene texto seleccionable. Sube otro archivo o pega el "
        "texto del syllabus."
    )
    name = escape_markdown(draft.file_name or "syllabus.pdf")
    st.error(
        f":red[**{name} · 0 caracteres de texto detectados**]\n\n"
        "Tus datos del curso están guardados. No se perdió nada."
    )
    with st.container(horizontal=True):
        if st.button("Pegar el texto", key="nc-paste"):
            draft.mode = PASTE
            _set_view("form")
            st.rerun()
        if st.button("Subir otro archivo", type="primary", key="nc-upload"):
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
