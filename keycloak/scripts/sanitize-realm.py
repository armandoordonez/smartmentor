#!/usr/bin/env python3
"""Quita de un export del realm todo lo que no debe versionarse.

Elimina: los usuarios con sus hashes de contraseña, los client secrets (y su fecha de creación) y los
proveedores de llaves de firma (llaves privadas, secretos HMAC y AES). Al importar el realm sin llaves,
Keycloak genera unas nuevas; sin secretos de cliente, genera uno nuevo por cada cliente confidencial.

Uso:
    python3 -I keycloak/scripts/sanitize-realm.py ENTRADA.json SALIDA.json

Lo ejecuta export-realm.sh. Solo usa la biblioteca estándar.
"""

import json
import sys
from pathlib import Path

KEY_PROVIDER = "org.keycloak.keys.KeyProvider"


def sanitize(realm: dict) -> dict:
    realm.pop("users", None)
    realm.pop("federatedUsers", None)
    for client in realm.get("clients", []):
        client.pop("secret", None)
        client.get("attributes", {}).pop("client.secret.creation.time", None)
    realm.get("components", {}).pop(KEY_PROVIDER, None)
    return realm


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    source, target = Path(argv[1]), Path(argv[2])
    realm = sanitize(json.loads(source.read_text(encoding="utf-8")))
    target.write_text(json.dumps(realm, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Realm sin secretos: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
