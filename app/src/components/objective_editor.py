"""Editor del objetivo (E4b): verbo de Bloom + contenido + criterio medible, con vista previa.

El componente solo exige que las tres partes no estén vacías para habilitar «Guardar»; la regla de
si el criterio es medible la aplica la API (`422 OBJECTIVE_NOT_MEASURABLE`) y la página muestra
su mensaje.
"""

from dataclasses import dataclass

import streamlit as st

from components.theme import BLOOM_VERBS


@dataclass(frozen=True)
class ObjectiveDraft:
    bloom_verb: str
    content: str
    criterion: str

    @property
    def is_complete(self) -> bool:
        return bool(self.bloom_verb.strip() and self.content.strip() and self.criterion.strip())

    @property
    def statement(self) -> str:
        parts = (self.bloom_verb.strip(), self.content.strip(), self.criterion.strip())
        return " ".join(part for part in parts if part).rstrip(".") + "."


@dataclass(frozen=True)
class ObjectiveEditorResult:
    draft: ObjectiveDraft
    save: bool
    cancel: bool
    reset_to_proposal: bool


def render_objective_editor(
    draft: ObjectiveDraft,
    *,
    key: str,
    topics_count: int | None = None,
    pass_threshold: int | None = None,
    can_reset: bool = True,
) -> ObjectiveEditorResult:
    """Formulario de las tres partes.

    `topics_count` alimenta «Con este objetivo tu ruta tiene N temas».
    """
    st.markdown("#### Editar tu objetivo")
    st.caption("Redáctalo como un resultado medible: verbo de Bloom + contenido + criterio.")
    verbs = list(BLOOM_VERBS)
    if draft.bloom_verb and draft.bloom_verb not in verbs:
        # La IA puede proponer un verbo fuera de la lista («Construir»): se conserva (B-020).
        verbs.insert(0, draft.bloom_verb)
    verb = st.selectbox(
        "Verbo de Bloom",
        verbs,
        index=verbs.index(draft.bloom_verb) if draft.bloom_verb in verbs else None,
        accept_new_options=True,
        key=f"{key}-verb",
    )
    st.caption("Recordar · Comprender · Aplicar · Analizar · Evaluar · Crear")
    content = st.text_input("Contenido", value=draft.content, key=f"{key}-content")
    criterion = st.text_input("Criterio medible", value=draft.criterion, key=f"{key}-criterion")
    st.caption(
        "Si el criterio no es medible, Guardar se desactiva: «Agrega cómo sabrás que lo lograste»."
    )
    current = ObjectiveDraft(verb or "", content, criterion)
    with st.container(key=f"panel-{key}-preview"):
        st.caption("**VISTA PREVIA**")
        st.markdown(f"**{current.statement}**" if current.is_complete else "—")
        if topics_count is not None:
            st.markdown(f"**Con este objetivo tu ruta tiene {topics_count} temas.**")
        if pass_threshold is not None:
            st.caption(
                f"El {pass_threshold} % para obtener el badge lo define tu instructor y no "
                "cambia con tu objetivo."
            )
    reset = (
        st.button("Volver a la propuesta de la IA", type="tertiary", key=f"{key}-reset")
        if can_reset
        else False
    )
    with st.container(horizontal=True):
        cancel = st.button("Cancelar", key=f"{key}-cancel")
        save = st.button(
            "Guardar objetivo",
            type="primary",
            key=f"{key}-save",
            disabled=not current.is_complete,
        )
    return ObjectiveEditorResult(current, save=save, cancel=cancel, reset_to_proposal=reset)
