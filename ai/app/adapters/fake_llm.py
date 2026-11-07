"""``FakeLlmProvider``: deterministic provider for tests, CI and local runs without keys.

* By default it answers each prompt with ``prompts/examples/llm/<prompt_id>.json`` (one valid
  provider answer per prompt, kept in sync with the schemas by the contract tests).
* ``item_review`` answers with an approving review of exactly the items it received, so any
  generated batch can be reviewed.
* Tests can queue scripted answers per prompt (a JSON string, an exception to raise or a
  function of the request) to simulate invalid JSON, provider errors or timeouts.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from collections.abc import Callable
from pathlib import Path

from app.ports.llm import LlmRequest, LlmResponse, LlmUsage

Scripted = str | BaseException | Callable[[LlmRequest], str]

_DATA_BLOCK = re.compile(r"^<<<\n(.*?)\n>>>$", re.DOTALL | re.MULTILINE)
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def last_data_block(user_prompt: str) -> str:
    blocks = _DATA_BLOCK.findall(user_prompt)
    return blocks[-1] if blocks else ""


def approving_item_review(request: LlmRequest) -> str:
    """Approve every item found in the ``items`` data block of an ``item_review`` prompt."""
    try:
        items = json.loads(last_data_block(request.user))
    except json.JSONDecodeError:
        items = []
    reviews = [
        {
            "item_id": str(item.get("item_id", "")),
            "single_correct_answer": True,
            "clear_stem": True,
            "bloom_matches": True,
            "aligned_with_outcome": True,
            "issues": [],
        }
        for item in items
        if isinstance(item, dict)
    ]
    return json.dumps({"reviews": reviews}, ensure_ascii=False)


class FakeLlmProvider:
    def __init__(self, examples_dir: Path) -> None:
        self._examples_dir = examples_dir
        self._scripts: defaultdict[str, deque[Scripted]] = defaultdict(deque)
        self._defaults: dict[str, Callable[[LlmRequest], str]] = {
            "item_review": approving_item_review
        }
        self.requests: list[LlmRequest] = []

    @property
    def name(self) -> str:
        return "fake"

    def script(self, prompt_id: str, *answers: Scripted) -> None:
        """Queue answers for the next calls of ``prompt_id`` (then back to the default)."""
        self._scripts[prompt_id].extend(answers)

    def set_default(self, prompt_id: str, answer: Callable[[LlmRequest], str]) -> None:
        self._defaults[prompt_id] = answer

    def calls(self, prompt_id: str) -> list[LlmRequest]:
        return [r for r in self.requests if r.prompt_id == prompt_id]

    def _default(self, request: LlmRequest) -> str:
        if request.prompt_id in self._defaults:
            return self._defaults[request.prompt_id](request)
        path = self._examples_dir / f"{request.prompt_id}.json"
        return path.read_text(encoding="utf-8")

    async def generate_structured(self, request: LlmRequest) -> LlmResponse:
        self.requests.append(request)
        queue = self._scripts.get(request.prompt_id)
        answer: Scripted = queue.popleft() if queue else self._default
        if isinstance(answer, BaseException):
            raise answer
        text = answer if isinstance(answer, str) else answer(request)
        usage = LlmUsage(
            input_tokens=estimate_tokens(request.system + request.user),
            output_tokens=estimate_tokens(text),
        )
        return LlmResponse(text=text, usage=usage, model=request.model)
