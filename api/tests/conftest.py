"""Configuración común de pruebas: variables de entorno antes de importar la aplicación."""

import os

os.environ.setdefault("DATABASE_PASSWORD", "test-password")
os.environ.setdefault("DATABASE_NAME", "smartmentor_test")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("OIDC_ISSUER_URL", "http://keycloak.test/realms/smartmentor")
os.environ.setdefault(
    "OIDC_JWKS_URL", "http://keycloak.test/realms/smartmentor/protocol/openid-connect/certs"
)
os.environ.setdefault("OIDC_AUDIENCE", "smartmentor-api")
os.environ.setdefault("LOG_LEVEL", "WARNING")
