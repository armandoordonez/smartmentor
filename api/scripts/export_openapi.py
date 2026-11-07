"""Regenera `docs/contracts/openapi-api.json` desde la aplicación.

Uso (lo envuelve `api/scripts/dev.sh openapi`): python -m scripts.export_openapi [ruta]
La prueba `tests/unit/test_openapi_contract.py` falla si el archivo publicado no coincide.
"""

import os
import sys
from pathlib import Path

# Valores desechables: generar el contrato no abre conexiones ni valida tokens.
os.environ.setdefault("DATABASE_PASSWORD", "test-only-not-a-secret")
os.environ.setdefault("OIDC_ISSUER_URL", "http://keycloak.test/realms/smartmentor")
os.environ.setdefault(
    "OIDC_JWKS_URL", "http://keycloak.test/realms/smartmentor/protocol/openid-connect/certs"
)

from app.core.openapi import render
from app.main import create_app

DEFAULT_TARGET = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "openapi-api.json"


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGET
    target.write_text(render(create_app()), encoding="utf-8")
    print(f"OpenAPI escrito en {target}")  # noqa: T201


if __name__ == "__main__":
    main()
