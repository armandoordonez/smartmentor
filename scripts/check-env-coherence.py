#!/usr/bin/env python3
"""Comprueba que .env.example y lo que lee el código sean coherentes (plan, sección 16.2).

Reglas:
1. Toda variable que referencia docker-compose.yml con ${VARIABLE} está documentada en .env.example.
2. Toda variable que leen los ``Settings`` de api/, app/ y ai/ (clases que heredan de ``BaseSettings``) está
   documentada en .env.example o la define el propio compose para el contenedor (por ejemplo, la API lee
   ``DATABASE_USER`` y el compose se la entrega desde ``API_DATABASE_USER``), o está en SETTINGS_INTERNAL.
3. Todo campo obligatorio de un ``Settings`` (sin valor por defecto) lo define el compose para algún servicio.
4. Todo marcador ${VARIABLE} del realm de Keycloak lo recibe el contenedor de Keycloak en el compose.
5. Toda variable documentada en .env.example se usa (compose, ``Settings``, scripts o realm) o está en
   FUTURE_VARIABLES, la lista explícita de variables reservadas para fases que aún no las leen.
6. Toda variable de FUTURE_VARIABLES sigue sin usarse (si alguien ya la usa, hay que quitarla de la lista).

Uso:  python3 -I scripts/check-env-coherence.py        (desde cualquier carpeta)
Solo usa la biblioteca estándar; conviene ejecutarlo con Python 3.12 (el del proyecto).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Variables documentadas que ningún servicio lee todavía, con la fase que las usará.
FUTURE_VARIABLES = {
    "METRICS_DATABASE_URL": "Fase 9: conexión del notebook de métricas (la lee el cuaderno, no un servicio)",
    "BADGE_ISSUER_NAME": "Fase 3: emisor de las insignias (Open Badges)",
    "BADGE_ISSUER_URL": "Fase 3: URL del emisor de las insignias",
}

# Campos de Settings que se pueden sobreescribir pero no forman parte de la configuración documentada.
SETTINGS_INTERNAL = {"APP_NAME", "APP_VERSION", "OIDC_IDENTITY_PROVIDER"}

SETTINGS_DIRS = ["api/app", "app/src", "ai/app"]
SCRIPT_GLOBS = ["**/*.sh", "database/bootstrap/*.sql", "database/scripts/*"]
SKIP_PARTS = {".venv", "node_modules", "__pycache__", "data", "backups", ".git"}

NAME = r"[A-Z][A-Z0-9_]*"


def env_example_keys() -> set[str]:
    keys = set()
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        match = re.match(rf"^({NAME})=", line)
        if match:
            keys.add(match.group(1))
    return keys


def compose_names() -> tuple[set[str], set[str]]:
    """(variables ${...} que referencia el compose, claves de entorno que define para los contenedores)."""
    lines = (ROOT / "docker-compose.yml").read_text(encoding="utf-8").splitlines()
    text = "\n".join(line for line in lines if not line.lstrip().startswith("#"))  # sin comentarios
    refs = set(re.findall(rf"(?<!\$)\$\{{({NAME})", text))
    env_keys = set(re.findall(rf"^\s+({NAME}):\s", text, flags=re.MULTILINE))
    return refs, env_keys


def realm_variables() -> set[str]:
    names: set[str] = set()
    for path in (ROOT / "keycloak" / "realm").glob("*.json"):
        names |= set(re.findall(rf"\$\{{({NAME})\}}", path.read_text(encoding="utf-8")))
    return names


def script_references(known: set[str]) -> set[str]:
    """Variables conocidas que leen los scripts (se ignoran las locales que no están en .env.example)."""
    found: set[str] = set()
    for pattern in SCRIPT_GLOBS:
        for path in ROOT.glob(pattern):
            if not path.is_file() or SKIP_PARTS & set(path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for name in re.findall(rf"\$\{{?({NAME})", text) + re.findall(rf"\\getenv\s+\w+\s+({NAME})", text):
                if name in known:
                    found.add(name)
    return found


class SettingsField:
    def __init__(self, env_names: set[str], required: bool, where: str) -> None:
        self.env_names = env_names
        self.required = required
        self.where = where


def _is_base_settings(node: ast.ClassDef, known: set[str]) -> bool:
    for base in node.bases:
        label = base.id if isinstance(base, ast.Name) else base.attr if isinstance(base, ast.Attribute) else ""
        if label == "BaseSettings" or label in known:
            return True
    return False


def _string_args(call: ast.Call) -> set[str]:
    return {arg.value for arg in call.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}


def _prefix(node: ast.ClassDef) -> str:
    for statement in node.body:
        targets = statement.targets if isinstance(statement, ast.Assign) else []
        if any(isinstance(t, ast.Name) and t.id == "model_config" for t in targets):
            for sub in ast.walk(statement.value):  # type: ignore[attr-defined]
                if isinstance(sub, ast.keyword) and sub.arg == "env_prefix" and isinstance(sub.value, ast.Constant):
                    return str(sub.value.value)
    return ""


def _analyze_field(statement: ast.AnnAssign, prefix: str, where: str) -> SettingsField | None:
    if not isinstance(statement.target, ast.Name) or statement.target.id.startswith("_"):
        return None
    name = statement.target.id
    value = statement.value
    required = value is None
    names = {(prefix + name).upper()}
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "Field":
        keywords = {kw.arg: kw.value for kw in value.keywords}
        has_default = "default" in keywords or "default_factory" in keywords or (
            bool(value.args) and not (isinstance(value.args[0], ast.Constant) and value.args[0].value is Ellipsis)
        )
        required = not has_default
        for alias_key in ("validation_alias", "alias"):
            alias = keywords.get(alias_key)
            if isinstance(alias, ast.Constant) and isinstance(alias.value, str):
                names = {alias.value.upper()}
            elif isinstance(alias, ast.Call):
                names = {s.upper() for s in _string_args(alias)} or names
    return SettingsField(names, required, where)


def settings_fields() -> list[SettingsField]:
    fields: list[SettingsField] = []
    known: set[str] = set()
    classes: list[tuple[Path, ast.ClassDef]] = []
    for directory in SETTINGS_DIRS:
        for path in sorted((ROOT / directory).rglob("*.py")):
            if SKIP_PARTS & set(path.parts):
                continue
            source = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source)
            except SyntaxError:
                # Sintaxis de Python 3.12 en un intérprete más viejo: solo importa si el archivo define Settings.
                if "BaseSettings" in source:
                    raise
                continue
            classes += [(path, n) for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    changed = True
    while changed:  # herencia entre clases de configuración
        changed = False
        for _, node in classes:
            if node.name not in known and _is_base_settings(node, known):
                known.add(node.name)
                changed = True
    for path, node in classes:
        if node.name not in known:
            continue
        prefix = _prefix(node)
        for statement in node.body:
            if isinstance(statement, ast.AnnAssign):
                field = _analyze_field(statement, prefix, f"{path.relative_to(ROOT)}:{node.name}")
                if field:
                    fields.append(field)
    return fields


def main() -> int:
    documented = env_example_keys()
    compose_refs, compose_env = compose_names()
    fields = settings_fields()
    settings_names = {n for f in fields for n in f.env_names}
    realm_vars = realm_variables()
    scripts = script_references(documented)

    problems: list[str] = []

    for name in sorted(compose_refs - documented):
        problems.append(f"docker-compose.yml usa ${{{name}}} y no está en .env.example")
    for name in sorted(settings_names - documented - compose_env - SETTINGS_INTERNAL):
        problems.append(f"un Settings lee {name} y no está en .env.example ni la define el compose")
    for field in fields:
        if field.required and not (field.env_names & (documented | compose_env)):
            problems.append(f"{field.where}: {sorted(field.env_names)} es obligatoria y el compose no la define")
    for name in sorted(realm_vars - compose_env):
        problems.append(f"el realm usa ${{{name}}} y el contenedor de Keycloak no la recibe en el compose")

    used = compose_refs | settings_names | scripts | realm_vars
    for name in sorted(documented - used - set(FUTURE_VARIABLES)):
        problems.append(f".env.example documenta {name} y nada la usa (bórrala o agrégala a FUTURE_VARIABLES)")
    for name in sorted(set(FUTURE_VARIABLES) & used):
        problems.append(f"{name} figura en FUTURE_VARIABLES pero ya se usa: quítala de la lista")
    for name in sorted(set(FUTURE_VARIABLES) - documented):
        problems.append(f"{name} figura en FUTURE_VARIABLES y no está en .env.example")

    print(f".env.example: {len(documented)} variables; compose: {len(compose_refs)} referencias; "
          f"Settings: {len(settings_names)} variables en {len(fields)} campos; scripts: {len(scripts)}; "
          f"realm: {len(realm_vars)}; futuras: {len(FUTURE_VARIABLES)}")
    for problem in problems:
        print(f"ERROR: {problem}")
    if not problems:
        print("Coherente.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
