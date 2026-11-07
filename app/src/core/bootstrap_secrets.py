"""Genera el `secrets.toml` de Streamlit desde variables de entorno, al arrancar el contenedor.

Streamlit solo lee la configuración de `st.login` de `secrets.toml`; para no versionar secretos ni
duplicar la configuración, este módulo lo escribe (con permisos 0600) a partir de las variables de
`.env`. Con `APP_DATA_SOURCE=fixtures` no hace nada: ese modo no pide login.

Uso (lo llama `docker-entrypoint.sh`):  python -m core.bootstrap_secrets
"""

import os
import sys
from pathlib import Path

from core.config import Settings, get_settings

REQUIRED = {
    "OIDC_UI_CLIENT_SECRET": "oidc_ui_client_secret",
    "APP_COOKIE_SECRET": "app_cookie_secret",
    "OIDC_SERVER_METADATA_URL": "oidc_server_metadata_url",
}


def secrets_path() -> Path:
    override = os.environ.get("STREAMLIT_SECRETS_FILE")
    return Path(override) if override else Path.home() / ".streamlit" / "secrets.toml"


def _quote(value: str) -> str:
    """Cadena TOML básica: escapa barra invertida, comillas y saltos de línea."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def missing_variables(settings: Settings) -> list[str]:
    return [name for name, field in REQUIRED.items() if not getattr(settings, field)]


def render_secrets(settings: Settings) -> str:
    """Contenido del `secrets.toml` (la sección `[auth]` y el proveedor `keycloak`)."""
    redirect_uri = f"{settings.app_public_url.rstrip('/')}/oauth2callback"
    return "\n".join(
        [
            "[auth]",
            f"redirect_uri = {_quote(redirect_uri)}",
            f"cookie_secret = {_quote(settings.app_cookie_secret)}",
            'expose_tokens = ["access", "id"]',
            "",
            "[auth.keycloak]",
            f"client_id = {_quote(settings.oidc_ui_client_id)}",
            f"client_secret = {_quote(settings.oidc_ui_client_secret)}",
            f"server_metadata_url = {_quote(settings.oidc_server_metadata_url or '')}",
            "",
        ]
    )


def main() -> int:
    settings = get_settings()
    if settings.app_data_source == "fixtures":
        sys.stdout.write("APP_DATA_SOURCE=fixtures: no se genera secrets.toml\n")
        return 0
    missing = missing_variables(settings)
    if missing:
        sys.stderr.write(f"Faltan variables de entorno para el login: {', '.join(missing)}\n")
        return 1
    path = secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_secrets(settings), encoding="utf-8")
    path.chmod(0o600)
    sys.stdout.write(f"secrets.toml generado en {path}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
