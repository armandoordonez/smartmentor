"""Preguntas de una en una (diagnóstico E3, quiz E6b y E6c, final E8, retención E14).

Dibuja la pregunta actual, guarda las respuestas en cada paso («guardado parcial») y entrega al
final. Qué se hace al guardar y al entregar lo decide la página con los callbacks; el avance entre
preguntas es solo de presentación.
"""

from collections.abc import Callable, Sequence
from contextlib import suppress
from typing import Literal

import streamlit as st
from streamlit.errors import StreamlitInvalidLayoutContextError

from clients.base import ApiError
from clients.models import AssessmentItem, LearnerAnswer
from components.layout import render_action_row, render_notice
from components.quiz_form import options_state, render_options, render_stem
from core.errors import defer_to_main, is_global, show_action_error
from core.learner_state import AnswerSheet
from core.widget_state import seed_defaults

DONT_KNOW_LABEL = "No lo sé"
SHORT_ANSWER_LIMIT = 500
# Consigna de la respuesta corta. Antes decía «Responde en 2 a 4 frases», que contradecía las
# preguntas que piden varias partes (p. ej. un diseño en 3 partes de la final, B-039). El límite
# de caracteres ya lo muestra el contador del campo; la consigna no fija un número de frases.
SHORT_ANSWER_HINT = "Responde todo lo que pide la pregunta, de forma breve."

NotesStyle = Literal["caption", "chip", "notice"]
"""Cómo se dibujan las notas: texto pequeño (diagnóstico), chip gris en la tarjeta (quiz y final,
V-035) o caja azul suave bajo la tarjeta (retención, V-054)."""


def _rerun(scope: Literal["app", "fragment"]) -> None:
    """Vuelve a dibujar solo el fragmento si se está en uno; si no (la primera carga o `AppTest`,
    que corre la página entera), la página."""
    if scope == "fragment":
        with suppress(StreamlitInvalidLayoutContextError):
            st.rerun(scope="fragment")
    st.rerun()


def _show_save_error(error: ApiError) -> None:
    """Error al guardar o entregar desde la hoja, que suele correr en un `st.fragment`.

    Un error global (401 por token vencido, 403 de rol) no se puede relanzar desde el fragmento
    (B-031): se deja para `main.py` con una ejecución completa. Las respuestas ya están en la hoja
    (`st.session_state`), así que no se pierden.
    """
    if is_global(error):
        defer_to_main(error)
    show_action_error(error)


def _is_answered(item: AssessmentItem, sheet: AnswerSheet) -> bool:
    answer = sheet.answers.get(item.item_id)
    if answer is None:
        return False
    if item.item_type == "short_answer":
        return bool((answer.text_answer or "").strip())
    return answer.dont_know or answer.selected_option is not None


def _question(
    item: AssessmentItem,
    sheet: AnswerSheet,
    key: str,
    *,
    hint: str | None,
) -> None:
    saved = sheet.answers.get(item.item_id)
    widget_key = f"{key}-{item.item_id}"
    if item.item_type == "multiple_choice":
        # El valor inicial entra por el estado de sesión y no pisa un borrador restaurado (B-054).
        seed_defaults(
            options_state(
                options=item.options,
                key=widget_key,
                selected=saved.selected_option if saved and not saved.dont_know else None,
            )
        )
        choice = render_options(stem=item.stem, options=item.options, key=widget_key)
        if choice is not None:
            sheet.answers[item.item_id] = LearnerAnswer(
                item_id=item.item_id, selected_option=choice
            )
        return
    render_stem(item.stem, key=widget_key)
    if hint:
        st.caption(hint)
    if saved and saved.text_answer:
        seed_defaults({f"answer-{widget_key}": saved.text_answer})
    text = st.text_area(
        "Tu respuesta",
        max_chars=SHORT_ANSWER_LIMIT,
        placeholder="Escribe tu respuesta…",
        label_visibility="collapsed",
        key=f"answer-{widget_key}",
    )
    if text.strip():
        sheet.answers[item.item_id] = LearnerAnswer(item_id=item.item_id, text_answer=text)
    elif item.item_id in sheet.answers:
        del sheet.answers[item.item_id]


def _render_rubric(item: AssessmentItem, key: str, *, notes: Sequence[str], card: bool) -> None:
    """«Cómo se califica» de una respuesta corta. En tarjeta (V-036) va en caja azul suave con las
    notas de la pregunta (Figma E6c)."""
    if not item.rubric_summary:
        return
    with st.container(key=f"card-rubric-{key}") if card else st.container():
        st.caption("**CÓMO SE CALIFICA**")
        st.markdown(item.rubric_summary)
        if card:
            for note in notes:
                st.caption(note)


def render_question_sheet(
    items: Sequence[AssessmentItem],
    sheet: AnswerSheet,
    *,
    key: str,
    save: Callable[[list[LearnerAnswer]], object],
    submit: Callable[[list[LearnerAnswer]], object],
    submit_label: str,
    notes: Sequence[str] | Callable[[AssessmentItem], Sequence[str]] = (),
    context: Callable[[AssessmentItem], str | None] | None = None,
    allow_dont_know: bool = False,
    hint: str | None = None,
    rerun_scope: Literal["auto", "app", "fragment"] = "auto",
    card: bool = False,
    notes_style: NotesStyle = "caption",
    progress: bool = True,
    leading_action: Callable[[], None] | None = None,
) -> None:
    """Pregunta actual, notas, «No lo sé» y botones Anterior y Siguiente (o el de entregar).

    Elegir una opción o escribir nunca recarga la página entera (B-018, B-022):
    - `"auto"` (por defecto): la hoja va en su propio `st.fragment`. Elegir solo redibuja la hoja;
      «No lo sé», Anterior y Siguiente guardan y recargan la página, para que el «Pregunta X de N»
      que la página muestra arriba se actualice.
    - `"fragment"`: la página ya puso la hoja (con su encabezado) dentro de un fragmento; todo,
      salvo entregar, redibuja solo ese fragmento y no vuelve a pedir datos a la API.
    - `"app"`: sin fragmento; cada interacción recarga la página.

    Entregar siempre recarga la página entera: lo que sigue lo decide el `next_action`.

    Presentación (V-034 a V-036, V-054): `progress` dibuja la barra «pregunta n de N» bajo el
    encabezado; `card` pone la pregunta en una tarjeta; `notes_style` elige cómo se ven las notas;
    `leading_action` dibuja un botón a la izquierda de Anterior (el «Ahora no» de la retención).
    """
    if rerun_scope == "auto":
        _sheet_fragment(
            items,
            sheet,
            key=key,
            save=save,
            submit=submit,
            submit_label=submit_label,
            notes=notes,
            context=context,
            allow_dont_know=allow_dont_know,
            hint=hint,
            nav_scope="app",
            card=card,
            notes_style=notes_style,
            progress=progress,
            leading_action=leading_action,
        )
        return
    _sheet(
        items,
        sheet,
        key=key,
        save=save,
        submit=submit,
        submit_label=submit_label,
        notes=notes,
        context=context,
        allow_dont_know=allow_dont_know,
        hint=hint,
        nav_scope=rerun_scope,
        card=card,
        notes_style=notes_style,
        progress=progress,
        leading_action=leading_action,
    )


def _sheet(
    items: Sequence[AssessmentItem],
    sheet: AnswerSheet,
    *,
    key: str,
    save: Callable[[list[LearnerAnswer]], object],
    submit: Callable[[list[LearnerAnswer]], object],
    submit_label: str,
    notes: Sequence[str] | Callable[[AssessmentItem], Sequence[str]],
    context: Callable[[AssessmentItem], str | None] | None,
    allow_dont_know: bool,
    hint: str | None,
    nav_scope: Literal["app", "fragment"],
    card: bool = False,
    notes_style: NotesStyle = "caption",
    progress: bool = True,
    leading_action: Callable[[], None] | None = None,
) -> None:
    if not items:
        st.info("Esta prueba todavía no tiene preguntas.")
        return
    index = min(sheet.index, len(items) - 1)
    item = items[index]
    is_short = item.item_type == "short_answer"
    line = context(item) if context is not None else None
    item_notes = tuple(notes(item) if callable(notes) else notes)
    chips = notes_style == "chip"
    # Respuesta corta con tarjeta (E6c): chip «Pregunta n de N · …» arriba, las notas en la caja
    # de la rúbrica y los botones debajo. Opción múltiple (E6b, E8): todo dentro de la tarjeta.
    boxed_rubric = card and is_short and bool(item.rubric_summary)
    actions_in_card = card and chips and not is_short
    if card and is_short:
        st.badge(
            f"Pregunta {index + 1} de {len(items)}" + (f" · {line}" if line else ""), color="blue"
        )
    if progress:
        st.progress((index + 1) / len(items))
    is_last = index == len(items) - 1
    result: list[bool] = []

    # Sin tarjeta (E3, V-037): «No lo sé» a la izquierda y «Anterior» y «Siguiente» a la derecha.
    split_nav = not card and not chips
    dont_know_in_nav: list[bool] = []

    def _nav(chip_notes: Sequence[str]) -> None:
        """«Anterior» y «Siguiente» (o entregar), con las notas en chip a la izquierda."""
        exits = None
        if chips:
            # Chips a la izquierda y botones a la derecha (E6b y E8).
            left, right = st.columns([2, 1], vertical_alignment="center")
            with left:
                for note in chip_notes:
                    st.badge(note, color="gray")
            buttons = right.container(
                horizontal=True, horizontal_alignment="right", key=f"nav-right-{key}"
            )
        elif split_nav:
            exits, buttons = render_action_row(f"nav-{key}")
        else:
            buttons = st.container(horizontal=True)
        if exits is not None:
            with exits:
                if leading_action is not None:
                    leading_action()
                if allow_dont_know and item.item_type == "multiple_choice":
                    # Enlace terciario, como en Figma (E3); el CSS lo pinta azul y subrayado.
                    dont_know_in_nav.append(
                        st.button(
                            DONT_KNOW_LABEL,
                            type="tertiary",
                            key=f"{key}-dont-know-{item.item_id}",
                        )
                    )
        with buttons:
            if exits is None and leading_action is not None:
                leading_action()
            back = st.button("Anterior", key=f"{key}-back", disabled=index == 0)
            forward = st.button(
                submit_label if is_last else "Siguiente",
                type="primary",
                key=f"{key}-next",
                disabled=not _is_answered(item, sheet),
            )
        result[:] = [back, forward]

    def _notes_after_card() -> None:
        for note in item_notes:
            if notes_style == "notice":
                render_notice(note, tone="info")
            elif not chips:
                st.caption(note)

    def _dont_know(pressed: bool) -> None:
        """«No lo sé» cuenta como respuesta: guarda y pasa a la siguiente pregunta.

        En la última se queda para que la persona entregue. Antes solo marcaba y no se veía ningún
        cambio (B-019).
        """
        if not pressed:
            return
        sheet.answers[item.item_id] = LearnerAnswer(item_id=item.item_id, dont_know=True)
        st.session_state.pop(f"option-{key}-{item.item_id}", None)
        try:
            save(list(sheet.answers.values()))
        except ApiError as error:
            _show_save_error(error)
            return
        if not is_last:
            sheet.index = index + 1
        _rerun(nav_scope)

    with st.container(key=f"card-quiz-{key}") if card else st.container():
        if line and not (card and is_short):
            st.badge(line, color="blue")
        _question(item, sheet, key, hint=hint)
        if not card:
            if item.rubric_summary:
                _render_rubric(item, key, notes=(), card=False)
            _notes_after_card()
        saved = sheet.answers.get(item.item_id)
        if saved is not None and saved.dont_know:
            st.caption(f"Respondiste «{DONT_KNOW_LABEL}». Puedes elegir una opción si la sabes.")
        if not split_nav:
            _dont_know(
                allow_dont_know
                and item.item_type == "multiple_choice"
                and st.button(DONT_KNOW_LABEL, key=f"{key}-dont-know-{item.item_id}")
            )
        if actions_in_card:
            _nav(item_notes)
    if card:
        if boxed_rubric:
            _render_rubric(item, key, notes=item_notes if chips else (), card=True)
            if not chips:
                _notes_after_card()
        else:
            if is_short and item.rubric_summary:
                _render_rubric(item, key, notes=(), card=True)
            _notes_after_card()
    if not actions_in_card:
        outside_chips = item_notes if chips and not boxed_rubric else ()
        _nav(outside_chips)
    if split_nav and dont_know_in_nav:
        _dont_know(dont_know_in_nav[0])
    back, forward = result
    if not (back or forward):
        return
    try:
        save(list(sheet.answers.values()))
        if back:
            sheet.index = index - 1
        elif is_last:
            submit(list(sheet.answers.values()))
        else:
            sheet.index = index + 1
    except ApiError as error:
        _show_save_error(error)
        return
    _rerun("app" if forward and is_last else nav_scope)


# La misma hoja como fragmento con identidad fija (`"auto"`): Streamlit la vuelve a llamar con los
# argumentos de la última ejecución completa de la página.
_sheet_fragment = st.fragment(_sheet)
