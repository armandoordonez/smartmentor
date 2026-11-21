"""``GET /v1/prompts`` (C4): catalog with versions and usage from ``llm_call_logs``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ContainerDep
from app.api.schemas import PromptBody, PromptCatalogResponse, PromptVersionBody
from app.core.errors import ApiError
from app.ports.call_logs import PromptUsage
from app.ports.prompts import PromptCatalogEntry, PromptNotFoundError, PromptStore

router = APIRouter(prefix="/v1/prompts", tags=["prompts"])


def _body(
    entry: PromptCatalogEntry,
    usage: dict[tuple[str, str], PromptUsage],
    store: PromptStore,
    *,
    with_text: bool,
) -> PromptBody:
    versions: list[PromptVersionBody] = []
    for version, digest in sorted(entry.versions.items()):
        used = usage.get((entry.id, f"v{version}"))
        calls = used.calls if used else 0
        system = user = None
        if with_text:
            try:
                template = store.get(entry.id, version)
                system, user = template.system, template.user
            except PromptNotFoundError:
                pass
        versions.append(
            PromptVersionBody(
                version=version,
                sha256=digest,
                calls=calls,
                invalid_output_rate=(used.invalid_output / calls) if used and calls else None,
                system=system,
                user=user,
            )
        )
    return PromptBody(
        id=entry.id,
        name_es=entry.name_es,
        task=entry.task,
        current_version=entry.current_version,
        model_tier=entry.model_tier,
        temperature=entry.temperature,
        output_schema=entry.output_schema,
        contract=entry.contract,
        screens=list(entry.screens),
        versions=versions,
    )


@router.get("")
async def list_prompts(container: ContainerDep) -> PromptCatalogResponse:
    usage = {(u.prompt_id, u.prompt_version): u for u in await container.call_logs.prompt_usage()}
    return PromptCatalogResponse(
        prompts=[
            _body(e, usage, container.prompts, with_text=False) for e in container.prompts.catalog()
        ]
    )


@router.get("/{prompt_id}")
async def get_prompt(prompt_id: str, container: ContainerDep) -> PromptBody:
    entry = next((e for e in container.prompts.catalog() if e.id == prompt_id), None)
    if entry is None:
        raise ApiError(404, "PROMPT_NOT_FOUND", f"Prompt {prompt_id[:60]} is not in the catalog.")
    usage = {(u.prompt_id, u.prompt_version): u for u in await container.call_logs.prompt_usage()}
    return _body(entry, usage, container.prompts, with_text=True)
