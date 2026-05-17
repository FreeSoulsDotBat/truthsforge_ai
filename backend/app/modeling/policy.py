from __future__ import annotations

from app.core.contracts import (
    ModelingExecutionMode,
    ModelingPlan,
    ModelingPlanStatus,
    ModelingRiskLevel,
    ModelingStepStatus,
)

BLOCKED_TOOL_PREFIXES = ("shell.", "filesystem.delete", "python.exec", "network.")

# Tools that never mutate the workspace; safe to auto-execute in any mode.
READ_ONLY_TOOL_NAMES = {
    "blender.measure_object",
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
    # Repair changes vertex/edge/face topology globally; cannot be undone without
    # a snapshot restore.
    "blender.repair_non_manifold",
}


def apply_modeling_policy(plan: ModelingPlan) -> ModelingPlan:
    """Apply local safety defaults before any MCP call can be executed."""
    steps = []
    for step in plan.steps:
        blocked = step.tool_name.startswith(BLOCKED_TOOL_PREFIXES)
        is_read_only = step.tool_name in READ_ONLY_TOOL_NAMES
        is_high_risk = (
            step.risk_level == ModelingRiskLevel.high or step.tool_name in HIGH_RISK_TOOL_NAMES
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
