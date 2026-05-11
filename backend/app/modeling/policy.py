from __future__ import annotations

from app.core.contracts import ModelingPlan, ModelingRiskLevel

BLOCKED_TOOL_PREFIXES = ("shell.", "filesystem.delete", "python.exec", "network.")

# Tools that never mutate the workspace; safe to auto-execute in any mode.
READ_ONLY_TOOL_NAMES = {
    "blender.validate_mesh",
    "blender.validate_printability",
    "fusion.validate_dimensions",
    "fusion.validate_printability",
    "project_store.list_snapshots",
}

HIGH_RISK_TOOL_NAMES = {
    "fusion.run_script",
    "blender.run_script",
    "project_store.restore_snapshot",
    # Boolean operations are non-reversible once the modifier is applied; they
    # mutate the geometry topology and may delete the auxiliary object.
    "blender.apply_boolean",
}


def apply_modeling_policy(plan: ModelingPlan) -> ModelingPlan:
    """Apply local safety defaults before any MCP call can be executed."""
    steps = []
    for step in plan.steps:
        blocked = step.tool_name.startswith(BLOCKED_TOOL_PREFIXES)
        is_read_only = step.tool_name in READ_ONLY_TOOL_NAMES
        requires_approval = not is_read_only and (
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
