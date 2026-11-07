"""Los modelos, los ejemplos del contrato y los fixtures dicen lo mismo.

- Los ejemplos JSON de `docs/contracts/api-v2.md` validan contra los modelos con `extra="forbid"`:
  si el contrato agrega o renombra un campo, la prueba falla y obliga a actualizar el modelo.
- Cada archivo de `tests/fixtures/` valida contra el modelo que le toca, también con `forbid`.
"""

import json
import re
from typing import Any

import pytest
from pydantic import BaseModel
from support import FIXTURES_DIR, REPO_ROOT

from clients import models
from clients.models import ApiModel, Page

CONTRACT = REPO_ROOT / "docs" / "contracts" / "api-v2.md"

# Primeras claves de cada ejemplo del contrato -> modelo.
CONTRACT_EXAMPLES: dict[tuple[str, ...], type[BaseModel]] = {
    ("id", "email"): models.Me,
    ("description", "education_level"): models.Profile,
    ("type", "step_id"): models.NextAction,
    ("id", "learning_path"): models.Enrollment,
    ("id", "status", "items"): models.Diagnostic,
    ("enrollment_id", "steps"): models.PathDetail,
    ("step_id", "topic"): models.StepContent,
    ("attempt_id", "status"): models.AttemptResult,
    ("job_id", "job_type"): models.Job,
}
# Ejemplos que modelan otros agentes (instructor y administrador).
OTHER_AGENT_EXAMPLES = {("name", "description")}


def _examples() -> list[dict[str, Any]]:
    text = CONTRACT.read_text(encoding="utf-8")
    return [json.loads(block) for block in re.findall(r"```json\n(.*?)```", text, re.DOTALL)]


def _fill_placeholders(value: Any) -> Any:
    """Los ejemplos citan esquemas de `prompts/schemas/` como «<grading.v1 sin meta>»."""
    if isinstance(value, str) and re.fullmatch(r"<[a-z_.0-9]+ sin meta>", value):
        return {}
    if isinstance(value, dict):
        return {key: _fill_placeholders(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_fill_placeholders(item) for item in value]
    return value


def _model_for(example: dict[str, Any]) -> type[BaseModel] | None:
    keys = tuple(example)
    for prefix, model in CONTRACT_EXAMPLES.items():
        if keys[: len(prefix)] == prefix:
            return model
    return None


def test_contract_file_has_examples() -> None:
    assert len(_examples()) >= 10


@pytest.mark.parametrize("example", _examples(), ids=lambda e: next(iter(e)))
def test_contract_example_validates_with_forbid(example: dict[str, Any]) -> None:
    model = _model_for(example)
    if model is None:
        assert tuple(example)[:2] in OTHER_AGENT_EXAMPLES, "ejemplo del contrato sin modelo"
        return
    model.model_validate(_fill_placeholders(example), extra="forbid")


# Prefijo del nombre del archivo -> modelo. El más largo gana.
FIXTURE_MODELS: dict[str, Any] = {
    "me_": models.Me,
    "profile": models.Profile,
    "consents": list[models.Consent],
    "learning_paths": Page[models.LearningPathCard],
    "enrollments_": Page[models.Enrollment],
    "enrollment_": models.Enrollment,
    "diagnostic_result": models.DiagnosticResult,
    "diagnostic": models.Diagnostic,
    "path": models.PathDetail,
    "step_content": models.StepContent,
    "attempt_result": models.AttemptResult,
    "attempt": models.Attempt,
    "review_plan": models.ReviewPlan,
    "badge": models.BadgeSummary,
    "job_accepted": models.JobAccepted,
    "job_": models.Job,
}


def _fixture_model(stem: str) -> Any:
    matches = [prefix for prefix in FIXTURE_MODELS if stem.startswith(prefix)]
    assert matches, f"fixture {stem} sin modelo en FIXTURE_MODELS"
    return FIXTURE_MODELS[max(matches, key=len)]


FIXTURE_FILES = sorted(FIXTURES_DIR.glob("*.json"))


def test_fixture_files_exist() -> None:
    assert len(FIXTURE_FILES) >= 20


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.stem)
def test_fixture_validates_with_forbid(path: Any) -> None:
    from pydantic import TypeAdapter

    data = json.loads(path.read_text(encoding="utf-8"))
    TypeAdapter(_fixture_model(path.stem)).validate_python(data, extra="forbid")


def test_models_ignore_unknown_fields_at_runtime() -> None:
    """La lectura normal es tolerante: un campo nuevo de la API no rompe la interfaz."""
    assert issubclass(models.Me, ApiModel)
    data = json.loads((FIXTURES_DIR / "me_learner.json").read_text(encoding="utf-8"))
    models.Me.model_validate({**data, "campo_nuevo": 1})


def test_fixture_personas_use_neutral_role_codes() -> None:
    for name in ("me_learner", "me_instructor", "me_admin"):
        data = json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))
        assert set(data["roles"]) <= {"learner", "instructor", "admin"}
        assert data["default_role"] in data["roles"]
        assert data["roles"] == sorted(data["roles"], key=["admin", "instructor", "learner"].index)
