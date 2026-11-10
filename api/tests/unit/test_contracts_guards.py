"""Guardias de contrato: OpenAPI publicado, catálogo de errores y rutas protegidas."""

import re
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.openapi import render
from app.main import create_app

ROOT = Path(__file__).resolve().parents[3]
APP_DIR = ROOT / "api" / "app"
OPENAPI_FILE = ROOT / "docs" / "contracts" / "openapi-api.json"
ERROR_CATALOG = ROOT / "docs" / "contracts" / "error-codes.md"

PUBLIC_PATHS = {
    "/health",
    "/ready",
    # Verificación «hosted» de Open Badges: pública por diseño (E10), por `public_id`.
    "/api/v1/badges/{public_id}/assertion.json",
    "/api/v1/badges/{public_id}/image.png",
}


def test_the_published_openapi_matches_the_code() -> None:
    expected = render(create_app())
    published = OPENAPI_FILE.read_text(encoding="utf-8")
    assert published == expected, (
        "docs/contracts/openapi-api.json está desactualizado: ejecuta "
        "`api/scripts/dev.sh openapi` y súbelo con el cambio de la API."
    )


def test_every_error_code_used_in_the_code_is_in_the_catalog() -> None:
    catalog = ERROR_CATALOG.read_text(encoding="utf-8")
    documented = set(re.findall(r"^\| `([A-Z][A-Z0-9_]*)`", catalog, flags=re.MULTILINE))
    assert "NOT_FOUND" in documented  # el análisis del catálogo funciona

    used: dict[str, str] = {}
    patterns = [
        r"\bcode\s*=\s*\"([A-Z][A-Z0-9_]+)\"",  # code="X" y code = "X"
        r"^\s+\"[a-z_0-9]+\": \(\s*\"([A-Z][A-Z0-9_]+)\",",  # constraint_messages
        r"^\s+\(\"([A-Z][A-Z0-9_]+)\",\s*$",
    ]
    for path in APP_DIR.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for pattern in patterns:
            for code in re.findall(pattern, source, flags=re.MULTILINE):
                used.setdefault(code, str(path.relative_to(ROOT)))
    used.pop("DOMAIN_ERROR", None)  # marcador de la clase base; nunca llega a una respuesta
    for code, file in used.items():
        # HTTP_<status> es el respaldo genérico del catálogo
        assert code in documented, (
            f"{code} (usado en {file}) no está en docs/contracts/error-codes.md"
        )
    assert {"COURSE_NOT_FOUND", "PREREQUISITE_CYCLE", "SYLLABUS_NO_TEXT", "LAST_ADMIN"} <= set(used)


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


async def test_every_api_route_rejects_requests_without_a_token() -> None:
    """Recorre el OpenAPI: toda ruta de `/api/v1` responde 401 sin token."""
    app = create_app()
    engine = create_engine(get_settings())  # perezoso: no abre conexiones
    app.state.session_factory = create_session_factory(engine)
    spec = app.openapi()
    checked = 0
    unprotected: list[str] = []
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as http:
        for path, operations in spec["paths"].items():
            if path in PUBLIC_PATHS:
                continue
            assert path.startswith("/api/v1/"), f"{path} no está bajo /api/v1"
            for method in operations:
                response = await http.request(method.upper(), _concrete(path))
                checked += 1
                if response.status_code != 401:
                    unprotected.append(f"{method.upper()} {path} -> {response.status_code}")
    await engine.dispose()
    assert checked > 40
    assert unprotected == []


def test_every_operation_has_a_summary_and_a_tag() -> None:
    spec = create_app().openapi()
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            assert operation.get("tags"), f"{method.upper()} {path} no tiene etiqueta"
            assert operation.get("operationId")


def test_no_old_vocabulary_survives_in_the_code() -> None:
    forbidden = re.compile(r"\b(student|teacher|estudiante|docente)s?\b", re.IGNORECASE)
    offenders = [
        str(path.relative_to(ROOT))
        for path in APP_DIR.rglob("*.py")
        if path.name != "labels.py"  # el glosario del perfil `academic` los usa a propósito
        and forbidden.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []
