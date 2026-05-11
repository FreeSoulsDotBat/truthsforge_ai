from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC

from app.core.contracts import AuditEvent, CostPolicy, ModelConfig, now_utc


@dataclass
class CostEstimate:
    tokens_in: int
    tokens_out: int
    estimated_cost_brl: float
    blocked: bool
    reason: str | None = None


def estimate_cost(
    model: ModelConfig,
    policy: CostPolicy,
    tokens_in: int,
    tokens_out: int,
    usd_to_brl: float = 5.0,
    current_spend_brl: float = 0,
) -> CostEstimate:
    input_cost = model.input_token_cost_per_million or 0
    output_cost = model.output_token_cost_per_million or 0
    usd = (tokens_in / 1_000_000 * input_cost) + (tokens_out / 1_000_000 * output_cost)
    brl = usd * usd_to_brl
    projected_spend_brl = current_spend_brl + brl
    blocked = policy.block_at_budget and projected_spend_brl > policy.monthly_budget_brl
    reason = None
    if blocked:
        reason = (
            "estimated_request_above_monthly_budget"
            if brl > policy.monthly_budget_brl
            else "estimated_monthly_budget_exceeded"
        )
    return CostEstimate(
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        estimated_cost_brl=round(brl, 6),
        blocked=blocked,
        reason=reason,
    )


def has_configured_pricing(model: ModelConfig) -> bool:
    return (
        model.input_token_cost_per_million is not None
        and model.input_token_cost_per_million > 0
        and model.output_token_cost_per_million is not None
        and model.output_token_cost_per_million > 0
    )


def estimate_tokens(text: str) -> int:
    # Cheap approximation for preflight cost governance without tokenizer dependencies.
    return max(1, len(text) // 4)


def monthly_spend(events: list[AuditEvent]) -> float:
    return round(sum(event.estimated_cost_brl for event in events), 6)


def current_month_key() -> str:
    return now_utc().astimezone(UTC).strftime("%Y-%m")


def monthly_events_for_store(store, month: str | None = None) -> list[AuditEvent]:
    target_month = month or current_month_key()
    if hasattr(store, "audit_events_for_month"):
        return store.audit_events_for_month(target_month)
    return [
        event
        for event in store.list_audit_events()
        if event.created_at.astimezone(UTC).strftime("%Y-%m") == target_month
    ]
