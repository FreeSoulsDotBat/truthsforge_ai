"""Safety policy applied to a freshly built :class:`ModelingPlan` before it
can be executed.

ADR-013 promotes :mod:`app.modeling.tool_registry` to single source of truth
for the allowlist. ``BLOCKED_TOOL_PREFIXES``, ``READ_ONLY_TOOL_NAMES`` and
``HIGH_RISK_TOOL_NAMES`` are re-exported here so legacy callers keep
working, but they always reflect the registry — there is no second copy to
drift from.

In v1 this module also tracked the ``ModelingExecutionMode``
(``plan_only`` / ``approval_required`` / ``safe_auto``). v2 collapses those
into a single chat-first flow, but during Ondas 1–3 the modes remain in the
contracts so the existing routes keep behaving the same. Once Onda 2
removes the modes the conditional on :class:`ModelingExecutionMode` can be
dropped entirely.
"""

from __future__ import annotations

from app.core.contracts import (
    ModelingExecutionMode,
    ModelingPlan,
    ModelingPlanStatus,
    ModelingRiskLevel,
    ModelingStepStatus,
)
from app.modeling.tool_registry import (
    BLOCKED_TOOL_PREFIXES,
    HIGH_RISK_TOOL_NAMES,
    READ_ONLY_TOOL_NAMES,
)
from app.modeling.tool_registry import (
    is_blocked as _is_blocked,
)
from app.modeling.tool_registry import (
    is_high_risk as _is_high_risk,
)
from app.modeling.tool_registry import (
    is_read_only as _is_read_only,
)

__all__ = [
    "BLOCKED_TOOL_PREFIXES",
    "HIGH_RISK_TOOL_NAMES",
    "READ_ONLY_TOOL_NAMES",
    "apply_modeling_policy",
]


def apply_modeling_policy(plan: ModelingPlan) -> ModelingPlan:
    """Apply local safety defaults before any MCP call can be executed.

    The function is idempotent: running it twice over the same plan
    produces the same result. It only mutates step ``status`` /
    ``approval_required`` / ``error`` and the plan ``status`` /
    ``approval_required``.
    """

    steps = []
    for step in plan.steps:
        blocked = _is_blocked(step.tool_name)
        is_read_only = _is_read_only(step.tool_name)
        is_high_risk = (
            step.risk_level == ModelingRiskLevel.high or _is_high_risk(step.tool_name)
        )
        requires_approval = not is_read_only and is_high_risk
        next_status = step.status
        if requires_approval and step.status == ModelingStepStatus.pending:
            next_status = ModelingStepStatus.waiting_approval
        if not requires_approval and step.status == ModelingStepStatus.waiting_approval:
            next_status = ModelingStepStatus.pending
        updates = {"approval_required": requires_approval, "status": next_status}
        if blocked:
            updates.update(
                {
                    "approval_required": True,
                    "status": ModelingStepStatus.waiting_approval,
                    "error": "Ferramenta bloqueada pela política local de modelagem 3D.",
                }
            )
        steps.append(step.model_copy(update=updates))
    approval_required = any(step.approval_required for step in steps)
    status = plan.status
    if plan.mode == ModelingExecutionMode.plan_only:
        status = ModelingPlanStatus.draft
    elif approval_required:
        status = ModelingPlanStatus.waiting_approval
    elif plan.status in {ModelingPlanStatus.draft, ModelingPlanStatus.waiting_approval}:
        status = ModelingPlanStatus.approved
    return plan.model_copy(
        update={
            "steps": steps,
            "approval_required": approval_required,
            "status": status,
        }
    )
