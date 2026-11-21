"""Prices per model from ``ai/config/prices.yaml`` (USD per million tokens, ADR 0011).

The owner fills the file after checking the provider's current rates (P-05). A configured model
without a price makes ``/ready`` fail; the cost of every call goes to ``llm_call_logs.cost_usd``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

MILLION = Decimal(1_000_000)
COST_QUANTUM = Decimal("0.000001")  # llm_call_logs.cost_usd is numeric(12,6)


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: Decimal
    output_per_million: Decimal

    def cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        total = (
            Decimal(input_tokens) * self.input_per_million
            + Decimal(output_tokens) * self.output_per_million
        ) / MILLION
        return total.quantize(COST_QUANTUM)


class PriceTable:
    def __init__(self, prices: dict[str, ModelPrice], issues: list[str] | None = None) -> None:
        self._prices = prices
        self.issues = issues or []

    @classmethod
    def load(cls, path: Path) -> PriceTable:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            return cls({}, [f"cannot read {path.name}: {exc.__class__.__name__}"])
        if raw.get("currency", "USD") != "USD" or raw.get("unit") != "per_million_tokens":
            return cls({}, [f"{path.name}: currency must be USD and unit per_million_tokens"])
        prices: dict[str, ModelPrice] = {}
        issues: list[str] = []
        for model, entry in (raw.get("models") or {}).items():
            try:
                price = ModelPrice(
                    input_per_million=Decimal(str(entry["input"])),
                    output_per_million=Decimal(str(entry.get("output", 0))),
                )
            except (KeyError, TypeError, InvalidOperation):
                issues.append(f"{path.name}: model {model} needs numeric input and output")
                continue
            if price.input_per_million < 0 or price.output_per_million < 0:
                issues.append(f"{path.name}: model {model} has a negative price")
                continue
            prices[str(model)] = price
        return cls(prices, issues)

    def get(self, model: str) -> ModelPrice | None:
        return self._prices.get(model)

    def cost(self, model: str, input_tokens: int, output_tokens: int) -> Decimal | None:
        price = self._prices.get(model)
        return None if price is None else price.cost(input_tokens, output_tokens)

    def missing(self, models: list[str]) -> list[str]:
        return [m for m in models if m not in self._prices]
