import fnmatch
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.contracts import ProviderModel, ProviderName

PRICING_PATH = Path(__file__).with_name("model_pricing.json")


@lru_cache(maxsize=1)
def _pricing_entries() -> list[dict[str, Any]]:
    payload = json.loads(PRICING_PATH.read_text(encoding="utf-8"))
    entries = payload.get("entries", [])
    return entries if isinstance(entries, list) else []


def _matches_model(model_id: str, patterns: object) -> bool:
    if not isinstance(patterns, list):
        return False
    normalized_id = model_id.lower()
    return any(
        isinstance(pattern, str) and fnmatch.fnmatch(normalized_id, pattern.lower())
        for pattern in patterns
    )


def provider_model_pricing(
    provider: ProviderName, model_id: str
) -> tuple[float, float, str | None, str | None] | None:
    for entry in _pricing_entries():
        if entry.get("provider") != provider.value:
            continue
        if not _matches_model(model_id, entry.get("patterns")):
            continue
        input_cost = entry.get("input_token_cost_per_million")
        output_cost = entry.get("output_token_cost_per_million")
        if not isinstance(input_cost, int | float) or not isinstance(output_cost, int | float):
            continue
        return float(input_cost), float(output_cost), entry.get("source"), entry.get("note")
    return None


def with_pricing(model: ProviderModel) -> ProviderModel:
    pricing = provider_model_pricing(model.provider, model.id)
    if pricing is None:
        return model
    input_cost, output_cost, source, note = pricing
    return model.model_copy(
        update={
            "input_token_cost_per_million": input_cost,
            "output_token_cost_per_million": output_cost,
            "pricing_source": source,
            "pricing_note": note,
        }
    )
