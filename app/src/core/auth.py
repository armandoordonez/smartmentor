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
  Al volver de Keycloak, Streamlit abre una sesión nueva en la raíz: `core/renewal.py` aparca
  antes la página y la sesión de la app para regresar a ellas (B-030).
- **Cuándo se renueva (B-040).** `plan_renewal` decide al inicio de cada ejecución. Si la trae una
  acción de la persona (un botón, un widget cambiado) y el token aún sirve para la petición (más de
  `EXPIRY_LEEWAY_SECONDS`), la acción sigue y la renovación se aplaza. Sin acción, se renueva antes
  de que venza (`PROACTIVE_RENEW_SECONDS`), en un momento en que no se interrumpe nada. Si el token
  ya no sirve, se renueva aparcando el borrador del formulario y el clic, que se repite al volver.
- `st.logout()` no cierra la sesión de Keycloak: `end_session_url` arma la redirección al
  `end_session_endpoint` del realm.

Estado de la verificación: las funciones puras (`token_expiry`, `is_token_expired`,
`build_end_session_url`) tienen pruebas; el flujo con un Keycloak real (7.0, prueba técnica del
login) queda pendiente de la Fase 8, que entrega el cliente `smartmentor-ui`.
"""

import base64
import json
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
import streamlit as st

from clients.base import ApiError
from core.config import get_settings

logger = logging.getLogger(__name__)

PROVIDER = "keycloak"
# Margen para que el token llegue vigente a la API: una petición tarda mucho menos (B-040). Con más
# margen, un clic poco antes del vencimiento se perdía aunque el token aún servía.
EXPIRY_LEEWAY_SECONDS = 15
# Sin acción de la persona, se renueva cuando faltan menos de 90 s (el token dura 5 min).
PROACTIVE_RENEW_SECONDS = 90
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


RenewalPlan = Literal["none", "now", "safe_point"]
"""`none`: no se renueva (el token sirve, o no se puede renovar y la página mostrará A7).
`now`: el token ya no sirve; se renueva antes de correr la página.
`safe_point`: el token sirve, pero vence pronto y no hay acción pendiente; se renueva ya."""


def plan_renewal(
    token: str | None,
    *,
    has_action: bool,
    now: datetime | None = None,
    leeway: int = EXPIRY_LEEWAY_SECONDS,
    margin: int = PROACTIVE_RENEW_SECONDS,
    min_age: int = RENEW_MIN_AGE_SECONDS,
) -> RenewalPlan:
    """Cuándo renovar el token en esta ejecución (B-040).

    - Con más de `margin` segundos por delante, no se renueva.
    - Con una acción pendiente y más de `leeway` segundos, se aplaza: la acción se hace con este
      token y la renovación queda para una ejecución sin acción.
    - Sin acción y con menos de `margin` segundos, se renueva ya (`safe_point`).
    - Con menos de `leeway` segundos, el token no sirve: se renueva (`now`).

    Como en `should_renew_silently`, solo se renueva un token emitido hace más de `min_age`
    segundos, para no entrar en un ciclo de redirecciones.
    """
    if token is None:
        return "none"
    expiry = token_expiry(token)
    issued = _claim_time(token, "iat")
    if expiry is None or issued is None:
        return "none"
    current = now or datetime.now(UTC)
    remaining = (expiry - current).total_seconds()
    if remaining > margin or (has_action and remaining > leeway):
        return "none"
    if (current - issued).total_seconds() <= min_age:
        return "none"
    return "safe_point" if remaining > leeway else "now"


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


def renewal_plan(*, has_action: bool) -> RenewalPlan:
    """`plan_renewal` con el access token de la sesión."""
    return plan_renewal(_exposed_token("access"), has_action=has_action)


def user_key() -> str | None:
    """Identidad estable de la persona (`sub` del token de identidad) para aparcar su sesión."""
    if not is_logged_in():
        return None
    try:
        value = st.user.get("sub") or st.user.get("email")
    except (AttributeError, KeyError):
        return None
    return str(value) if value else None


def renew_silently_if_possible(before_redirect: Callable[[], None] | None = None) -> bool:
    """Si el token venció pero la sesión de Keycloak puede seguir viva, repite el login.

    `st.login` solo encola la redirección del navegador: el guion sigue hasta el final. Devuelve
    True si se pidió la renovación, para que quien llama se detenga (`st.stop`) sin dibujar A7.
    `before_redirect` corre justo antes, para aparcar la página y la sesión (B-030): al volver,
    Streamlit abre una sesión nueva en la raíz. Si no aplica, devuelve False y la página sigue
    con A7.
    """
    if not should_renew_silently(_exposed_token("access")):
        return False
    logger.info("Access token vencido: se renueva con la sesión SSO de Keycloak")
    if before_redirect is not None:
        before_redirect()
    st.login(PROVIDER)
    return True


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
