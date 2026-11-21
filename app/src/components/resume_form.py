"""Hoja de vida (E2b y E15): estudios, cargo, años de experiencia, herramientas, idioma y nivel.

Recibe los valores actuales y devuelve los que eligió la persona; la página los guarda con
`PUT /me/profile`. Las herramientas que la persona agrega en «+ Agregar» las guarda la página en
la sesión y las vuelve a pasar en `extra_tools` (el componente no toca `st.session_state`).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import streamlit as st

from clients.models import CefrLevel, EducationLevel, ExperienceBand
from components.theme import (
    COMMON_TOOLS,
    EDUCATION_LEVEL_LABEL,
    EXPERIENCE_BAND_LABEL,
    LANGUAGE_LABEL,
)

CEFR_LEVELS: tuple[CefrLevel, ...] = ("A1", "A2", "B1", "B2", "C1", "C2")
_NOT_SELECTED = "Selecciona"


@dataclass(frozen=True)
class ResumeValues:
    education_level: EducationLevel | None = None
    qualification_title: str = ""
    job_title: str = ""
    experience_band: ExperienceBand | None = None
    tools: tuple[str, ...] = ()
    languages: tuple[tuple[str, CefrLevel], ...] = ()
    """(código del idioma, nivel MCER)."""


@dataclass(frozen=True)
class ResumeFormResult:
    values: ResumeValues
    added_tool: str | None = None
    """Herramienta nueva escrita en «+ Agregar»; la página la suma a `extra_tools`."""


def resume_form_state(values: ResumeValues, *, key: str) -> dict[str, Any]:
    """Valor inicial de cada widget con `key` del formulario, para ponerlo en `st.session_state`.

    Los widgets no llevan `value=`, `index=` ni `default=`: el valor inicial entra solo por el
    estado de sesión. Así, al restaurar un borrador antes de dibujar la página (B-040), Streamlit
    no avisa de que el widget tiene un valor por defecto y otro por la API de estado de sesión
    (B-053). La página lo aplica con `widget_state.seed_defaults`, que no pisa lo ya escrito.
    """
    state: dict[str, Any] = {}
    if values.education_level in EDUCATION_LEVEL_LABEL:
        state[f"{key}-education"] = values.education_level
    if values.qualification_title:
        state[f"{key}-title"] = values.qualification_title
    if values.job_title:
        state[f"{key}-job"] = values.job_title
    if values.experience_band in EXPERIENCE_BAND_LABEL:
        state[f"{key}-experience"] = values.experience_band
    if values.tools:
        state[f"{key}-tools"] = list(values.tools)
    for position, (code, cefr) in enumerate(_language_rows(values.languages)):
        if code in LANGUAGE_LABEL:
            state[f"{key}-language-{position}"] = code
        state[f"{key}-cefr-{position}"] = cefr
    return state


def tool_options(selected: Sequence[str], extra_tools: Sequence[str]) -> list[str]:
    """Herramientas ofrecidas: las comunes, las agregadas y las ya elegidas, sin repetir."""
    options: list[str] = []
    for tool in (*COMMON_TOOLS, *extra_tools, *selected):
        if tool not in options:
            options.append(tool)
    return options


def render_resume_form(
    values: ResumeValues,
    *,
    key: str,
    extra_tools: Sequence[str] = (),
) -> ResumeFormResult:
    """Las dos tarjetas de la hoja de vida: «Estudios y experiencia» y «Herramientas e idiomas»."""
    education_options = list(EDUCATION_LEVEL_LABEL)
    experience_options = list(EXPERIENCE_BAND_LABEL)
    # Sin `value=` ni `default=` e `index=None`: el valor inicial va por `resume_form_state`.
    with st.container(key=f"card-{key}-studies"):
        st.markdown("**Estudios y experiencia**")
        level_col, title_col = st.columns(2)
        level = level_col.selectbox(
            "Nivel máximo de estudios",
            education_options,
            index=None,
            format_func=lambda code: EDUCATION_LEVEL_LABEL[code],
            placeholder=_NOT_SELECTED,
            key=f"{key}-education",
        )
        title = title_col.text_input("Título", key=f"{key}-title")
        job_col, experience_col = st.columns(2)
        job = job_col.text_input("Cargo actual", key=f"{key}-job")
        experience = experience_col.selectbox(
            "Años de experiencia",
            experience_options,
            index=None,
            format_func=lambda code: EXPERIENCE_BAND_LABEL[code],
            placeholder=_NOT_SELECTED,
            key=f"{key}-experience",
        )
    added: str | None = None
    with st.container(key=f"card-{key}-tools"):
        st.markdown("**Herramientas e idiomas**")
        chosen = st.pills(
            "Herramientas",
            tool_options(values.tools, extra_tools),
            selection_mode="multi",
            label_visibility="collapsed",
            key=f"{key}-tools",
        )
        with st.popover("+ Agregar", type="tertiary"):
            new_tool = st.text_input("Otra herramienta", key=f"{key}-new-tool")
            if st.button("Agregar herramienta", key=f"{key}-add-tool") and new_tool.strip():
                added = new_tool.strip()
        st.caption("Toca para marcar las que usas.")
        languages = _render_languages(_language_rows(values.languages), key)
    resolved = ResumeValues(
        education_level=level,
        qualification_title=title.strip(),
        job_title=job.strip(),
        experience_band=experience,
        tools=tuple(chosen),
        languages=languages,
    )
    return ResumeFormResult(values=resolved, added_tool=added)


def _language_rows(
    current: tuple[tuple[str, CefrLevel], ...],
) -> list[tuple[str, CefrLevel]]:
    """Una fila por idioma del perfil, y una vacía si no hay ninguno."""
    return list(current) or [("", "A1")]


def _render_languages(
    rows: list[tuple[str, CefrLevel]], key: str
) -> tuple[tuple[str, CefrLevel], ...]:
    """Una fila «Idioma» y «Nivel» por idioma del perfil (al menos una)."""
    codes = list(LANGUAGE_LABEL)
    result: list[tuple[str, CefrLevel]] = []
    for position, _ in enumerate(rows):
        language_col, level_col = st.columns(2)
        picked = language_col.selectbox(
            "Idioma",
            codes,
            index=None,
            format_func=lambda value: LANGUAGE_LABEL[value],
            placeholder=_NOT_SELECTED,
            key=f"{key}-language-{position}",
        )
        level = level_col.selectbox(
            "Nivel",
            list(CEFR_LEVELS),
            key=f"{key}-cefr-{position}",
        )
        if picked is not None and level is not None:
            result.append((picked, level))
    return tuple(result)


def render_weights_card(*, weights: tuple[int, int, int] = (80, 10, 10), key: str) -> bool:
    """«Cómo usamos tu hoja de vida»: pesos del nivel. Devuelve True si pide ver sus derechos."""
    test, resume, profile = weights
    with st.container(key=f"card-{key}-weights"):
        st.markdown("**Cómo usamos tu hoja de vida**")
        for label, value in (
            ("Evaluación diagnóstica", test),
            ("Hoja de vida", resume),
            ("Descripción de tu perfil", profile),
        ):
            name_col, value_col = st.columns([4, 1])
            name_col.markdown(label)
            value_col.markdown(f"**{value} %**")
        st.caption(
            "Tus respuestas pesan más que cualquier dato previo. Si dejas la hoja de vida para "
            "después, su peso pasa al diagnóstico y tu ruta se recalcula sola cuando la completes."
        )
        st.caption(
            "Tu instructor solo ve tus herramientas e idiomas. No pedimos fecha de nacimiento, "
            "dirección ni foto."
        )
        return st.button(
            "Tus derechos y quién ve cada dato →", type="tertiary", key=f"{key}-rights"
        )
