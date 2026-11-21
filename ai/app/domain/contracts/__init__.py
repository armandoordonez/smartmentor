"""AI contracts: ``...LLM`` provider schemas, API contracts and their code checks.

Source of ``prompts/schemas/*.v1.json`` (exported with ``ai/scripts/export_schemas.py``).
"""

from app.domain.contracts.registry import CONTRACTS, LLM_SCHEMAS, SCHEMA_VERSION

__all__ = ["CONTRACTS", "LLM_SCHEMAS", "SCHEMA_VERSION"]
