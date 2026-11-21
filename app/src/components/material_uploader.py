"""Cargador de apuntes y lecturas del curso (R-004 en D1b, R-010 en D2).

Dibuja el cargador de varios archivos y, por cada uno, su fila con el tamaño, el «Origen» (que la
API guarda como licencia de la fuente del RAG) y su estado. Devuelve los archivos que se pueden
enviar y si hay más de los permitidos; la página decide qué hacer con ellos. Figma no dibuja este
bloque: sigue el estilo de la fila del syllabus de D1b.
"""

import re
from typing import Final

import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from clients.models_staff import MaterialOrigin
from components.formatting import file_size

MaterialFile = tuple[str, bytes, MaterialOrigin]
"""Nombre, contenido y origen de un apunte listo para enviar."""

MATERIAL_TYPES: Final = ["pdf", "txt", "md"]
MATERIAL_ORIGINS: Final[dict[MaterialOrigin, str]] = {
    "own_notes": "Apuntes propios",
    "open_license": "Libro o material abierto",
    "permitted": "Otro, con permiso de uso",
}

# Rechazos de la API que solo omiten ese apunte: el resto de la carga sigue y se avisa.
SKIPPABLE_MATERIAL_ERRORS: Final = frozenset(
    {
        "MATERIAL_NO_TEXT",
        "MATERIAL_UNSUPPORTED_TYPE",
        "MATERIAL_TOO_LARGE",
        "MATERIAL_LIMIT_REACHED",
    }
)


def escape_markdown(text: str) -> str:
    """Un nombre de archivo se muestra tal cual, sin que lo interprete el Markdown."""
    return re.sub(r"([\\\[\]*_`])", r"\\\1", text)


def render_material_uploader(
    key: str, *, max_files: int, max_bytes: int
) -> tuple[list[MaterialFile], bool]:
    """Cargador y filas de los apuntes; devuelve `(listos para enviar, sobran archivos)`.

    Un archivo de más de `max_bytes` se marca «Muy pesado» y no se envía. `key` distingue el
    cargador de cada pantalla y es el prefijo de las claves de sus widgets.
    """
    uploads: list[UploadedFile] = (
        st.file_uploader(
            "Arrastra aquí tus apuntes, guías o capítulos de libros abiertos",
            type=MATERIAL_TYPES,
            accept_multiple_files=True,
            key=key,
        )
        or []
    )
    st.caption(
        f"o haz clic para elegir archivos · PDF, TXT o MD, hasta {max_files} archivos de "
        f"{max_bytes // (1024 * 1024)} MB cada uno"
    )
    ready: list[MaterialFile] = []
    for upload in uploads:
        too_big = upload.size > max_bytes
        with st.container(horizontal=True, key=f"material-row-{key}-{upload.file_id}"):
            st.markdown(f"{escape_markdown(upload.name)} · {file_size(upload.size)}")
            st.space("stretch")
            origin: MaterialOrigin = st.selectbox(
                "Origen",
                list(MATERIAL_ORIGINS),
                format_func=MATERIAL_ORIGINS.__getitem__,
                key=f"{key}-origin-{upload.file_id}",
                label_visibility="collapsed",
                width=240,
            )
            if too_big:
                st.badge("Muy pesado", color="orange")
            else:
                st.badge("Listo", color="green")
                ready.append((upload.name, upload.getvalue(), origin))
    return ready, len(uploads) > max_files
