#!/usr/bin/env python3
"""Deja un export del realm listo para versionarse y comprueba que no lleve secretos.

Quita: los usuarios con sus hashes de contraseña, los proveedores de llaves de firma (llaves privadas,
secretos HMAC y AES) y el secreto de todo cliente confidencial. Después pone marcadores ``${VARIABLE}``
donde Keycloak debe tomar el valor del entorno al importar (comprobado con Keycloak 26.8.0):

* el secreto de ``smartmentor-ui`` y de ``smartmentor-api-service`` (``CLIENT_SECRET_VARIABLES``);
* la sección de correo ``smtpServer`` completa (``SMTP_*``).

Los demás clientes confidenciales quedan sin secreto: Keycloak genera uno al importar.

Uso:
    python3 -I keycloak/scripts/sanitize-realm.py ENTRADA.json SALIDA.json   # sanea un export
    python3 -I keycloak/scripts/sanitize-realm.py --check ARCHIVO.json       # solo comprueba

Lo ejecuta export-realm.sh y la CI (modo ``--check``). Solo usa la biblioteca estándar.
"""

import json
import re
import sys
from pathlib import Path

KEY_PROVIDER = "org.keycloak.keys.KeyProvider"

# Cliente -> variable de entorno de la que Keycloak toma su secreto al importar.
CLIENT_SECRET_VARIABLES = {
    "smartmentor-ui": "OIDC_UI_CLIENT_SECRET",
    "smartmentor-api-service": "AI_CLIENT_SECRET",
}

# Sección de correo: campo de Keycloak -> variable de entorno (plan, sección 18.6).
SMTP_VARIABLES = {
    "host": "SMTP_HOST",
    "port": "SMTP_PORT",
    "from": "SMTP_FROM",
    "fromDisplayName": "SMTP_FROM_DISPLAY_NAME",
    "starttls": "SMTP_STARTTLS",
    "user": "SMTP_USER",
    "password": "SMTP_PASSWORD",
}
# Valores fijos de la sección de correo (no son secretos ni dependen del despliegue).
SMTP_FIXED = {"ssl": "false", "auth": "true"}

PLACEHOLDER = re.compile(r"^\$\{[A-Z][A-Z0-9_]*\}$")


def placeholder(variable: str) -> str:
    return "${" + variable + "}"


UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
ID_FIELDS = ("id", "containerId")


def strip_ids(node: object) -> None:
    """Quita los identificadores internos (UUID) para que Keycloak genere los suyos al importar.

    Sin esto, importar el realm en una base donde ya existe otro realm con los mismos identificadores
    (por ejemplo uno renombrado) falla con «duplicate key». Las referencias del realm son por nombre.
    """
    if isinstance(node, dict):
        for field in ID_FIELDS:
            if isinstance(node.get(field), str) and UUID.match(node[field]):
                del node[field]
        for value in node.values():
            strip_ids(value)
    elif isinstance(node, list):
        for item in node:
            strip_ids(item)


def sanitize(realm: dict) -> dict:
    realm.pop("users", None)
    realm.pop("federatedUsers", None)
    for client in realm.get("clients", []):
        client.pop("secret", None)
        client.get("attributes", {}).pop("client.secret.creation.time", None)
        variable = CLIENT_SECRET_VARIABLES.get(client.get("clientId", ""))
        if variable:
            client["secret"] = placeholder(variable)
    realm.get("components", {}).pop(KEY_PROVIDER, None)
    realm["smtpServer"] = {
        **{field: placeholder(variable) for field, variable in SMTP_VARIABLES.items()},
        **SMTP_FIXED,
    }
    strip_ids(realm)
    return realm


def check(realm: dict) -> list[str]:
    """Devuelve los problemas que impiden versionar el realm (lista vacía = correcto)."""
    problems: list[str] = []
    if realm.get("users") or realm.get("federatedUsers"):
        problems.append("el realm trae usuarios")
    if KEY_PROVIDER in realm.get("components", {}):
        problems.append("el realm trae proveedores de llaves de firma")
    for client in realm.get("clients", []):
        secret = client.get("secret")
        if secret is not None and not PLACEHOLDER.match(secret):
            problems.append(f"el cliente {client.get('clientId')} trae un secreto literal")
    for field in ("password", "user", "host", "from"):
        value = realm.get("smtpServer", {}).get(field)
        if value and not PLACEHOLDER.match(value):
            problems.append(f"smtpServer.{field} es literal; debe ser un marcador ${{SMTP_...}}")
    if realm.get("registrationAllowed") and not realm.get("verifyEmail"):
        problems.append("autorregistro sin verifyEmail (G-01)")
    if not realm.get("bruteForceProtected"):
        problems.append("falta la protección de fuerza bruta (G-02)")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "--check":
        problems = check(json.loads(Path(argv[2]).read_text(encoding="utf-8")))
        for problem in problems:
            print(f"ERROR: {problem}")
        if not problems:
            print(f"Realm sin secretos: {argv[2]}")
        return 1 if problems else 0
    if len(argv) != 3:
        print(__doc__)
        return 2
    source, target = Path(argv[1]), Path(argv[2])
    realm = sanitize(json.loads(source.read_text(encoding="utf-8")))
    target.write_text(json.dumps(realm, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    problems = check(realm)
    for problem in problems:
        print(f"ERROR: {problem}")
    print(f"Realm sin secretos: {target}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
