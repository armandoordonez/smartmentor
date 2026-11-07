"""OpenAPI publicado en `docs/contracts/openapi-api.json` y su guardia (plan 18.2).

El documento depende solo del código: se normaliza lo que cambia con el entorno (la URL del
endpoint de tokens de Keycloak) para que la prueba sea la misma en cualquier máquina.
"""

import json
from typing import Any

from fastapi import FastAPI

TOKEN_URL_PLACEHOLDER = "{OIDC_ISSUER_URL}/protocol/openid-connect/token"  # noqa: S105


def contract_of(app: FastAPI) -> dict[str, Any]:
    spec = app.openapi()
    for scheme in spec.get("components", {}).get("securitySchemes", {}).values():
        password = scheme.get("flows", {}).get("password")
        if password is not None:
            password["tokenUrl"] = TOKEN_URL_PLACEHOLDER
    normalized: dict[str, Any] = json.loads(json.dumps(spec))
    return normalized


def render(app: FastAPI) -> str:
    """El texto exacto del archivo publicado (estable: claves ordenadas, salto de línea final)."""
    return json.dumps(contract_of(app), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
