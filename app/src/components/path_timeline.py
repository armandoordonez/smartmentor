"""Temas de la ruta en orden, con su estado (E5, filas «Tema 1» a «Tema 6» de Figma)."""

from collections.abc import Sequence

import streamlit as st

from clients.models import PathProgress, PathSettings, PathStep, Topic
from components.formatting import percent
from components.theme import (
    FINAL_AVAILABLE_BADGE,
    FINAL_LOCKED_BADGE,
    FINAL_PASSED_BADGE,
    STEP_BADGE,
    BadgeStyle,
)


def step_detail(step: PathStep, topic: Topic, settings: PathSettings) -> str:
    match step.status:
        case "skipped":
            return f"Omitido: ya lo dominas ({percent(step.diagnostic_score or 0)})"
        case "approved" if step.attempts_used <= 1:
            return f"Aprobado al primer intento · {percent(step.last_score or 0)}"
        case "approved":
            return f"Aprobado en el intento {step.attempts_used} · {percent(step.last_score or 0)}"
        case "in_progress" if step.attempts_used:
            return (
                f"Intento {min(step.attempts_used + 1, settings.max_attempts)} de "
                f"{settings.max_attempts} · último puntaje {percent(step.last_score or 0)}"
            )
        case _:
            return f"Video + lectura + quiz · ~{topic.estimated_minutes} min"


def _row(
    number: int,
    title: str,
    detail: str,
    badge: BadgeStyle,
    *,
    current: bool,
    action_key: str | None,
) -> bool:
    with st.container(border=True):
        columns = st.columns([0.35, 11, 2.2, 0.6], vertical_alignment="center")
        columns[0].markdown(f":gray[**{number}**]")
        with columns[1].container(gap=None):
            st.markdown(f":blue[**{title}**]" if current else f"**{title}**")
            st.caption(detail)
        with columns[2].container(horizontal=True, horizontal_alignment="right"):
            st.badge(badge[0], color=badge[1])
        if action_key is None:
            return False
        return columns[3].button(
            "",
            key=action_key,
            icon=":material/chevron_right:",
            type="tertiary",
            help="Abrir",
        )


def render_path_timeline(
    steps: Sequence[tuple[Topic, PathStep]], progress: PathProgress
) -> int | None:
    """Dibuja los temas y la evaluación final. Devuelve el id del tema que se quiere abrir, o
    -1 si se pidió abrir la evaluación final."""
    opened: int | None = None
    for number, (topic, step) in enumerate(steps, start=1):
        if _row(
            number,
            topic.title,
            step_detail(step, topic, progress.settings),
            STEP_BADGE[step.status],
            current=step.status == "in_progress",
            action_key=f"open-topic-{topic.id}",
        ):
            opened = topic.id

    threshold = percent(progress.settings.final_threshold)
    if progress.final_passed:
        detail, badge = "Aprobada · badge emitido", FINAL_PASSED_BADGE
    elif progress.final_available:
        detail, badge = f"Ya puedes presentarla · aprueba con {threshold}", FINAL_AVAILABLE_BADGE
    else:
        detail = f"Se habilita al completar los temas · aprueba con {threshold}"
        badge = FINAL_LOCKED_BADGE
    if _row(
        len(steps) + 1,
        "Evaluación final",
        detail,
        badge,
        current=progress.final_available,
        action_key="open-final" if progress.final_available or progress.final_passed else None,
    ):
        opened = -1
    return opened
