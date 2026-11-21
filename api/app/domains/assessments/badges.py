"""Badge Open Badges 2.0 con verificación «hosted» (E10): aserción e imagen.

La aserción solo lleva datos con hash: el receptor es `sha256(correo + sal)` (badge.v1), nunca el
correo ni el nombre. La imagen es un PNG generado sin dependencias (un emblema de color plano), para
que el enlace público funcione sin almacenamiento de archivos.
"""

import hashlib
import secrets
import struct
import zlib
from datetime import datetime
from typing import Any
from uuid import UUID

ASSERTION_PATH = "/api/v1/badges/{public_id}/assertion.json"
IMAGE_PATH = "/api/v1/badges/{public_id}/image.png"


def hashed_recipient(email: str, salt: str | None = None) -> dict[str, Any]:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.sha256((email.strip().lower() + salt).encode()).hexdigest()
    return {"type": "email", "hashed": True, "salt": salt, "identity": f"sha256${digest}"}


def build_assertion(
    *,
    public_id: UUID,
    base_url: str,
    email: str,
    issued_on: datetime,
    course_name: str,
    path_name: str,
    objective: str | None,
    topic_names: list[str],
    final_score: float,
    final_pass_threshold: float,
    issuer_name: str,
    issuer_url: str,
) -> dict[str, Any]:
    """Aserción `badge.v1` (Open Badges 2.0, verificación hosted)."""
    base = base_url.rstrip("/")
    assertion_url = base + ASSERTION_PATH.format(public_id=public_id)
    image_url = base + IMAGE_PATH.format(public_id=public_id)
    narrative = (
        f"Aprobó la evaluación final de la ruta «{path_name}» con {final_score:.0f} % "
        f"(umbral {final_pass_threshold:.0f} %)."
    )
    description = objective or f"Completó la ruta de aprendizaje «{path_name}»."
    return {
        "@context": "https://w3id.org/openbadges/v2",
        "type": "Assertion",
        "id": assertion_url,
        "recipient": hashed_recipient(email),
        "badge": {
            "type": "BadgeClass",
            "id": f"{assertion_url}#badge",
            "name": course_name[:80],
            "description": description,
            "image": image_url,
            "criteria": {
                "narrative": (
                    "Completar todos los temas de la ruta (aprobados u omitidos por dominio) y "
                    f"obtener al menos {final_pass_threshold:.0f} % en la evaluación final."
                )
            },
            "issuer": {
                "type": "Profile",
                "id": f"{issuer_url.rstrip('/')}#issuer",
                "name": issuer_name,
                "url": issuer_url,
            },
            "tags": topic_names[:10],
        },
        "issuedOn": issued_on.isoformat().replace("+00:00", "Z"),
        "verification": {"type": "hosted"},
        "evidence": [{"narrative": narrative}],
    }


def with_base_url(assertion: dict[str, Any], base_url: str) -> dict[str, Any]:
    """La aserción guardada lleva rutas relativas; al servirla se completan con la URL pública."""
    base = base_url.rstrip("/")

    def absolute(value: str) -> str:
        return base + value if value.startswith("/") else value

    badge = dict(assertion["badge"])
    badge["id"] = absolute(badge["id"])
    badge["image"] = absolute(badge["image"])
    return {**assertion, "id": absolute(assertion["id"]), "badge": badge}


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def badge_png(seed: str, size: int = 128) -> bytes:
    """Un emblema circular de color derivado de `seed` (PNG RGBA válido)."""
    digest = hashlib.sha256(seed.encode()).digest()
    color = bytes((40 + digest[0] % 120, 70 + digest[1] % 120, 120 + digest[2] % 120, 255))
    ring = bytes((255, 255, 255, 255))
    clear = bytes((0, 0, 0, 0))
    center = (size - 1) / 2
    radius = size / 2 - 2
    rows = bytearray()
    for y in range(size):
        rows.append(0)  # filtro «None» de la fila
        for x in range(size):
            distance = ((x - center) ** 2 + (y - center) ** 2) ** 0.5
            if distance > radius:
                rows += clear
            elif distance > radius - 6:
                rows += ring
            else:
                rows += color
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _chunk(b"IEND", b"")
    )
