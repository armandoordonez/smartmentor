"""C4 · La lista de `services/staff_prompts.py` sigue a `prompts/catalog.yaml` (M-008).

C4 no tiene ruta en la API: muestra una copia del catálogo. Si alguien publica un prompt v2 o
agrega uno nuevo en `prompts/`, esta prueba avisa que hay que actualizar la copia.

La app no depende de PyYAML, así que el catálogo se lee con una expresión regular: cada entrada
empieza con `- id:` y trae `current_version` y `name_es` (formato fijo, ver su encabezado).
"""

import re

from support import APP_DIR

from services.staff_prompts import PROMPTS

CATALOG = APP_DIR.parent / "prompts" / "catalog.yaml"
ENTRY = re.compile(r"^  - id: (?P<id>\S+)\n(?P<body>(?:^    .*\n?)*)", re.MULTILINE)


def _field(body: str, name: str) -> str:
    found = re.search(rf"^    {name}: (.+)$", body, re.MULTILINE)
    assert found is not None, f"falta {name} en catalog.yaml"
    return found.group(1).strip().strip('"')


def _catalog() -> list[tuple[str, int, str]]:
    text = CATALOG.read_text("utf-8")
    return [
        (m["id"], int(_field(m["body"], "current_version")), _field(m["body"], "name_es"))
        for m in ENTRY.finditer(text)
    ]


def test_c4_lists_the_same_prompts_versions_and_names_as_the_catalog() -> None:
    catalog = _catalog()
    assert catalog, "no se leyó ningún prompt de catalog.yaml"
    assert [(p.prompt_id, p.version, p.name) for p in PROMPTS] == catalog
