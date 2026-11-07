"""A3 y A3b · Primer ingreso y consentimiento (CU-34).

Después del primer login la persona acepta el tratamiento de sus datos (obligatorio) y decide si
participa en el piloto (opcional). Mientras `GET /me` diga `requires_consent`, `main.py` solo
registra esta página y la de derechos (A3c). Registrar la autorización es una llamada a la API
(`POST /me/consents`); la interfaz no decide nada por su cuenta.
"""

import streamlit as st

from clients.base import ApiError
from components.consent_form import render_consent_form, render_informed_consent
from core.config import get_settings
from core.container import get_client
from core.errors import show_action_error
from core.identity import current_me, refresh_me
from core.navigation import DATA_RIGHTS, home_for
from core.session import get_session

DOCUMENT_VERSION = "1.0"

settings = get_settings()
session = get_session()
me = current_me()

if not me.requires_consent:
    if session.consent_done:
        # Recién aceptó: `main.py` ya registra todas las páginas, así que se puede entrar al inicio.
        session.consent_done = False
        st.switch_page(home_for(session.active_role or me.default_role))
    st.title("Autorizaciones", anchor=False)
    st.success("Ya aceptaste el tratamiento de tus datos.", icon=":material/check_circle:")
    pilot = me.consent_status.pilot_research
    st.caption(
        "Participas en el piloto de investigación."
        if pilot.granted
        else "No participas en el piloto de investigación."
    )
    if st.button("Tus derechos y quién ve cada dato →", type="tertiary"):
        st.switch_page(DATA_RIGHTS)
    st.stop()

if session.consent_step == "informed":
    result = render_informed_consent(
        key="consent-informed",
        pilot_window=settings.pilot_window_text,
        participate_default=session.accept_pilot,
    )
    session.accept_pilot = result.participate
    if result.show_rights:
        st.switch_page(DATA_RIGHTS)
    if result.back or result.proceed:
        session.consent_step = "terms"
        st.rerun()
    st.stop()

form = render_consent_form(
    key="consent-terms",
    data_default=session.accept_data,
    pilot_default=session.accept_pilot,
)
session.accept_data = form.data_processing
session.accept_pilot = form.pilot_research
if form.read_informed:
    session.consent_step = "informed"
    st.rerun()
if form.submit:
    client = get_client()
    try:
        client.grant_consent("data_processing", DOCUMENT_VERSION)
        if form.pilot_research:
            client.grant_consent("pilot_research", DOCUMENT_VERSION)
    except ApiError as error:
        show_action_error(error)
    else:
        refresh_me()
        session.consent_done = True
        st.rerun()  # vuelve a armar la navegación completa (antes solo había consentimiento)
