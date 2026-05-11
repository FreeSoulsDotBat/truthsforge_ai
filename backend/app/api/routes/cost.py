from fastapi import APIRouter

from app.core.contracts import CostPolicy, CostUsage
from app.cost_governor.service import current_month_key, monthly_events_for_store, monthly_spend
from app.storage.store import get_store

router = APIRouter()


@router.get("/policy", response_model=CostPolicy)
def get_policy() -> CostPolicy:
    return get_store().get_cost_policy()


@router.post("/policy", response_model=CostPolicy)
def update_policy(payload: CostPolicy) -> CostPolicy:
    return get_store().set_cost_policy(payload)


@router.get("/usage", response_model=CostUsage)
def get_usage() -> CostUsage:
    store = get_store()
    policy = store.get_cost_policy()
    month = current_month_key()
    events = monthly_events_for_store(store, month)
    spend = monthly_spend(events)
    return CostUsage(
        month=month,
        monthly_budget_brl=policy.monthly_budget_brl,
        estimated_spend_brl=spend,
        remaining_budget_brl=round(max(policy.monthly_budget_brl - spend, 0), 6),
        warn_threshold_percent=policy.warn_threshold_percent,
        block_at_budget=policy.block_at_budget,
        request_count=len(events),
        tokens_in=sum(event.tokens_in for event in events),
        tokens_out=sum(event.tokens_out for event in events),
    )
