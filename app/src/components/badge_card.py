"""Badge de la ruta completada (E10) y tarjetas de logros (E12)."""

import json
from typing import Literal

import streamlit as st

from clients.models import Badge, LearningPath
from components.formatting import duration, percent, short_date

BadgeAction = Literal["achievements"]


def _open_badge_json(badge: Badge, earner: str) -> str:
    """Aserción con la forma de Open Badges 2.0 (la emisión firmada la hará la API)."""
    return json.dumps(
        {
            "@context": "https://w3id.org/openbadges/v2",
            "type": "Assertion",
            "id": badge.verification_url,
            "recipient": {"type": "name", "identity": earner, "hashed": False},
            "badge": {
                "type": "BadgeClass",
                "name": badge.path_title,
                "issuer": {"type": "Profile", "name": "SmartMentor"},
            },
            "issuedOn": badge.issued_on.isoformat(),
            "evidence": {"narrative": f"Evaluación final: {percent(badge.final_score)}"},
        },
        ensure_ascii=False,
        indent=2,
    )


def render_badge_hero(badge: Badge, earner: str) -> BadgeAction | None:
    with st.container(horizontal_alignment="center"):
        st.markdown("# :blue[:material/workspace_premium:]", width="content")
        st.title("¡Ruta completada!", anchor=False, width="content")
        st.caption(
            f"Obtuviste {percent(badge.final_score)} en la evaluación final de {badge.path_title}.",
            width="content",
        )
        with st.container(border=True, horizontal=True, gap="large", width="content"):
            st.metric("Evaluación final", percent(badge.final_score), width="content")
            st.metric(
                "Temas dominados",
                f"{badge.mastered_topics} / {badge.total_topics}",
                width="content",
            )
            st.metric("Ahorrados", duration(badge.saved_minutes), width="content")
        st.caption(
            f"Formato Open Badges · imagen + JSON · enlace público de verificación · "
            f"emitido el {short_date(badge.issued_on)}",
            width="content",
        )
        with st.container(horizontal=True, horizontal_alignment="center"):
            with st.popover("Compartir"):
                st.caption("Enlace público de verificación")
                st.code(badge.verification_url, language=None)
            st.download_button(
                "Descargar badge",
                data=_open_badge_json(badge, earner),
                file_name=f"badge-{badge.learning_path_id}.json",
                mime="application/json",
                type="primary",
                on_click="ignore",
            )
            if st.button("Ver mis logros"):
                return "achievements"
    return None


def render_badge_slot(path: LearningPath, badge: Badge | None, *, enrolled: bool) -> bool:
    """Tarjeta de un logro. Devuelve True si se pide ver el badge."""
    with st.container(border=True, height="stretch"):
        if badge is not None:
            st.markdown("## :blue[:material/workspace_premium:]")
        else:
            st.markdown("## :gray[:material/lock:]")
        st.markdown(f"#### {path.short_title if badge else path.title}")
        if badge is not None:
            st.caption(f"Obtenido {short_date(badge.issued_on)} · {percent(badge.final_score)}")
            return st.button("Ver badge", key=f"view-badge-{path.id}")
        st.caption(
            "Bloqueado · completa la ruta para obtenerlo"
            if enrolled
            else "Bloqueado · inscríbete para obtenerlo"
        )
        return False
