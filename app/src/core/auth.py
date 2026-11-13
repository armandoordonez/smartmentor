"""Autenticación con Keycloak (`st.login`) y manejo del token (ADR 0006 y 0017).

- No hay secretos aquí: Streamlit lee `[auth]` del `secrets.toml` que `core/bootstrap_secrets.py`
  genera al arrancar desde variables de entorno.
- El access token vive en el servidor (`st.user.tokens`, con `expose_tokens`); nunca llega al
  navegador ni a los registros. Solo se **lee** su `exp` para decidir si pedir un nuevo login: la
  firma y el `aud` los valida la API.
- La cookie de sesión de Streamlit dura 30 días y no sigue el vencimiento del token, así que
  `access_token()` revisa `exp` antes de cada llamada.
- **Renovación silenciosa.** Streamlit no expone el refresh token, así que el access token (corto,
  5 min en el realm) se renueva repitiendo `st.login`: mientras la sesión SSO de Keycloak siga viva
  (3 h, `ssoSessionIdleTimeout` y `ssoSessionMaxLifespan`), Keycloak devuelve un token nuevo sin
  pedir contraseña ni OTP. Cuando la sesión SSO vence, Keycloak muestra su login. Para no entrar en
  un ciclo de redirecciones, solo se renueva si el token vencido se emitió hace más de
  `RENEW_MIN_AGE_SECONDS` (`should_renew_silently`); si no, la app muestra A7 «Tu sesión expiró».
- `st.logout()` no cierra la sesión de Keycloak: `end_session_url` arma la redirección al
  `end_session_endpoint` del realm.

Estado de la verificación: las funciones puras (`token_expiry`, `is_token_expired`,
`build_end_session_url`) tienen pruebas; el flujo con un Keycloak real (7.0, prueba técnica del
login) queda pendiente de la Fase 8, que entrega el cliente `smartmentor-ui`.
"""

import base64
import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
import streamlit as st

from clients.base import ApiError
from core.config import get_settings

logger = logging.getLogger(__name__)

PROVIDER = "keycloak"
EXPIRY_LEEWAY_SECONDS = 30
RENEW_MIN_AGE_SECONDS = 120
TOKEN_EXPIRED_CODE = "TOKEN_EXPIRED"  # noqa: S105 (código de error de la API, no un secreto)
_END_SESSION_KEY = "end_session_url"


# --- Funciones puras (con pruebas) -------------------------------------------------------------


def _claim_time(token: str, claim: str) -> datetime | None:
    try:
        payload = token.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        claims: Any = json.loads(base64.urlsafe_b64decode(padded))
        return datetime.fromtimestamp(float(claims[claim]), tz=UTC)
    except (IndexError, ValueError, KeyError, TypeError):
        return None


def token_expiry(token: str) -> datetime | None:
    """Lee el `exp` de un JWT **sin validar la firma** (solo para decidir si pedir otro login)."""
    return _claim_time(token, "exp")


def should_renew_silently(
    token: str | None, *, now: datetime | None = None, min_age: int = RENEW_MIN_AGE_SECONDS
) -> bool:
    """True si conviene pedir un token nuevo a Keycloak sin mostrar A7.

    Solo para un token vencido que se emitió hace más de `min_age` segundos: si el token recién
    renovado ya llega vencido (reloj desfasado, realm mal configurado), renovar otra vez sería un
    ciclo infinito de redirecciones, y es mejor mostrar A7.
    """
    if token is None or not is_token_expired(token, now=now):
        return False
    issued = _claim_time(token, "iat")
    if issued is None:
        return False
    current = now or datetime.now(UTC)
    return (current - issued).total_seconds() > min_age


def is_token_expired(
    token: str, *, now: datetime | None = None, leeway: int = EXPIRY_LEEWAY_SECONDS
) -> bool:
    """True si el token venció o vence en menos de `leeway` segundos (sin `exp`, venció)."""
    expiry = token_expiry(token)
    if expiry is None:
        return True
    current = now or datetime.now(UTC)
    return (expiry - current).total_seconds() <= leeway


def build_end_session_url(
    metadata: Mapping[str, Any], *, id_token: str | None, post_logout_redirect_uri: str
) -> str | None:
    """URL del `end_session_endpoint` con `id_token_hint` y regreso a la app (OIDC RP-Initiated)."""
    endpoint = metadata.get("end_session_endpoint")
    if not isinstance(endpoint, str):
        return None
    params = {"post_logout_redirect_uri": post_logout_redirect_uri}
    if id_token:
        params["id_token_hint"] = id_token
    else:
        params["client_id"] = get_settings().oidc_ui_client_id
    return f"{endpoint}?{urlencode(params)}"


# --- Streamlit ---------------------------------------------------------------------------------


def is_logged_in() -> bool:
    return bool(getattr(st.user, "is_logged_in", False))


def _exposed_token(name: str) -> str | None:
    tokens = getattr(st.user, "tokens", None)
    if tokens is None:
        return None
    try:
        value = tokens.get(name)
    except (AttributeError, KeyError):
        return None
    return str(value) if value else None


def access_token() -> str:
    """Access token vigente; lanza `ApiError(401)` si falta o venció (la página muestra A7)."""
    token = _exposed_token("access")
    if token is None or is_token_expired(token):
        raise ApiError(401, TOKEN_EXPIRED_CODE, "access token missing or expired")
    return token


def renew_silently_if_possible() -> None:
    """Si el token venció pero la sesión de Keycloak puede seguir viva, repite el login.

    `st.login` redirige el navegador y no regresa; si no aplica, la función no hace nada y la
    página sigue con A7.
    """
    if should_renew_silently(_exposed_token("access")):
        logger.info("Access token vencido: se renueva con la sesión SSO de Keycloak")
        st.login(PROVIDER)


def login() -> None:
    """Redirige al login de Keycloak."""
    st.login(PROVIDER)


def _fetch_metadata() -> Mapping[str, Any]:
    url = get_settings().oidc_server_metadata_url
    if not url:
        return {}
    try:
        response = httpx.get(url, timeout=3.0)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("No se pudo leer el descubrimiento OIDC para cerrar la sesión")
        return {}
    return data if isinstance(data, dict) else {}


def logout() -> None:
    """Cierra la sesión de Streamlit y deja la URL para cerrar también la de Keycloak.

    La redirección al `end_session_endpoint` se ofrece en la pantalla de despedida como un enlace
    (`pending_end_session_url`): Streamlit no permite redirigir el navegador desde el servidor.
    """
    url = build_end_session_url(
        _fetch_metadata(),
        id_token=_exposed_token("id"),
        post_logout_redirect_uri=get_settings().app_public_url,
    )
    st.session_state[_END_SESSION_KEY] = url
    st.logout()


def pending_end_session_url() -> str | None:
    value = st.session_state.get(_END_SESSION_KEY)
    return value if isinstance(value, str) else None


def clear_end_session_url() -> None:
    st.session_state.pop(_END_SESSION_KEY, None)
