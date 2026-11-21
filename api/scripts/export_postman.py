"""Regenera la colección de Postman desde docs/contracts/openapi-api.json (`dev.sh postman`)."""

import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[2]
spec = json.loads((root / "docs/contracts/openapi-api.json").read_text(encoding="utf-8"))
target = root / "api/postman/SmartMentor.postman_collection.json"
collection = json.loads(target.read_text(encoding="utf-8"))
schemas = spec["components"]["schemas"]


def resolve(schema):
    if "$ref" in schema:
        return resolve(schemas[schema["$ref"].split("/")[-1]])
    return schema


def example(schema, depth=0):
    schema = resolve(schema)
    if "anyOf" in schema:
        options = [o for o in schema["anyOf"] if o.get("type") != "null"]
        return example(options[0], depth) if options else None
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "object" or "properties" in schema:
        if depth > 3:
            return {}
        required = set(schema.get("required", []))
        return {
            k: example(v, depth + 1)
            for k, v in schema.get("properties", {}).items()
            if k in required
        }
    if t == "array":
        return [] if depth > 2 else [example(schema.get("items", {}), depth + 1)]
    if t == "integer":
        return schema.get("minimum", 1) if "minimum" in schema else 1
    if t == "number":
        return 1
    if t == "boolean":
        return False
    if "default" in schema and schema["default"] is not None:
        return schema["default"]
    return "texto"


folders: dict[str, list] = {}
for path, operations in spec["paths"].items():
    for method, op in operations.items():
        tag = op["tags"][0]
        url_path = re.sub(r"\{([a-z_]+)\}", r"{{\1}}", path)
        headers = []
        query = []
        for param in op.get("parameters", []):
            if param["in"] == "header" and param["name"] == "Idempotency-Key":
                headers.append({"key": "Idempotency-Key", "value": "{{$guid}}"})
            elif param["in"] == "query" and not param.get("required"):
                query.append({"key": param["name"], "value": "", "disabled": True})
        request = {
            "method": method.upper(),
            "header": headers,
            "url": {
                "raw": "{{base_url}}" + url_path,
                "host": ["{{base_url}}"],
                "path": url_path.strip("/").split("/"),
                "query": query,
            },
            "description": op.get("summary", "") + "\n\n" + (op.get("description") or ""),
        }
        body = op.get("requestBody", {}).get("content", {})
        if "multipart/form-data" in body and "application/json" in body:
            request["body"] = {
                "mode": "formdata",
                "formdata": [{"key": "file", "type": "file", "src": []}],
            }
            request["description"] += '\n\nTambién acepta JSON: {"text": "..."}.'
        elif "application/json" in body:
            request["header"].append({"key": "Content-Type", "value": "application/json"})
            request["body"] = {
                "mode": "raw",
                "raw": json.dumps(
                    example(body["application/json"]["schema"]), indent=2, ensure_ascii=False
                ),
                "options": {"raw": {"language": "json"}},
            }
        folders.setdefault(tag, []).append({"name": f"{method.upper()} {path}", "request": request})

collection["item"] = [{"name": tag, "item": items} for tag, items in sorted(folders.items())]
collection["info"]["description"] = (
    "Colección de la API de SmartMentor v2 (generada desde docs/contracts/openapi-api.json con "
    "api/scripts/dev.sh postman). Antes de cada petición un script pide a Keycloak el token con "
    "usuario y contraseña (cliente smartmentor-dev-tools, solo desarrollo) y lo envía como Bearer. "
    "Configura username y password en el entorno «SmartMentor local». Las variables de ruta "
    "({{course_id}}, {{topic_id}}, {{job_id}}...) se definen en el entorno."
)
target.write_text(json.dumps(collection, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(sum(len(v) for v in folders.values()), "peticiones en", len(folders), "carpetas")  # noqa: T201
