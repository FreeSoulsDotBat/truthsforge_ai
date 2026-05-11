from __future__ import annotations

from app.core.contracts import ModelingPlan, ModelingRiskLevel

BLOCKED_TOOL_PREFIXES = ("shell.", "filesystem.delete", "python.exec", "network.")
HIGH_RISK_TOOL_NAMES = {
    "fusion.run_script",
    "blender.run_script",
    "project_store.restore_snapshot",
}


def apply_modeling_policy(plan: ModelingPlan) -> ModelingPlan:
    """Apply local safety defaults before any MCP call can be executed."""
    steps = []
    for step in plan.steps:
        blocked = step.tool_name.startswith(BLOCKED_TOOL_PREFIXES)
        requires_approval = (
            step.approval_required
            or step.risk_level in {ModelingRiskLevel.medium, ModelingRiskLevel.high}
            or step.tool_name in HIGH_RISK_TOOL_NAMES
        )
        updates = {"approval_required": requires_approval}
        if blocked:
            updates.update(
                {
                    "approval_required": True,
                    "error": "Ferramenta bloqueada pela política local de modelagem 3D.",
                }
            )
        steps.append(step.model_copy(update=updates))
    return plan.model_copy(
        update={
            "steps": steps,
            "approval_required": any(step.approval_required for step in steps),
        }
    )
