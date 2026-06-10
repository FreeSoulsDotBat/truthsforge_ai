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
    ModelingApprovalDecision,
    ModelingApprovalRequest,
    ModelingExecutionMode,
    ModelingPlan,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingStepStatus,
    now_utc,
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
    requires_approval as _requires_approval,
)

__all__ = [
    "BLOCKED_TOOL_PREFIXES",
    "HIGH_RISK_TOOL_NAMES",
    "READ_ONLY_TOOL_NAMES",
    "apply_modeling_policy",
    "apply_plan_approval",
]


def apply_plan_approval(plan: ModelingPlan, payload: ModelingApprovalRequest) -> ModelingPlan:
    """Aplica a decisão de aprovação a um plano — mutação pura (sem persistir/auditar).

    Fonte única (DT-006) usada por ``ModelingService.approve_plan`` e
    ``ModelingChatOrchestrator``. Rejeição → ``rejected``. Aprovação → promove
    os steps ``approval_required`` de ``waiting_approval`` para ``approved``
    (marcando ``approved_at``) e o plano vira ``approved``. Os steps que não
    exigem aprovação ficam intactos. Idempotente no caso normal.
    """

    if payload.decision == ModelingApprovalDecision.reject:
        return plan.model_copy(
            update={"status": ModelingPlanStatus.rejected, "updated_at": now_utc()}
        )

    steps = []
    for step in plan.steps:
        if step.approval_required and step.status == ModelingStepStatus.waiting_approval:
            # Só carimba approved_at quando a transição real waiting_approval ->
            # approved acontece; assim a função volta a ser idempotente e steps
            # pending/failed não recebem um approved_at contraditório.
            steps.append(
                step.model_copy(
                    update={"status": ModelingStepStatus.approved, "approved_at": now_utc()}
                )
            )
        else:
            steps.append(step)
    return plan.model_copy(
        update={
            "status": ModelingPlanStatus.approved,
            "steps": steps,
            "updated_at": now_utc(),
        }
    )


def _declarative_combines(step: ModelingPlanStep) -> bool:
    """F7 — a expansão deste passo declarativo funde corpos (combine-DENTRO)?
    ``distribute_along`` com ``alternate`` funde os nós no corpo-pai
    (``combine_bodies``, high_risk). Marcar como aprovação-requerida no PLANO faz o
    card de aprovação disclosar o combine ANTES de qualquer execução (escolha do
    dono: human-in-the-loop p/ a fusão), em vez de bloquear a expansão no meio."""

    if step.tool_name == "fusion.distribute_along":
        alt = (step.input_json or {}).get("alternate")
        return isinstance(alt, (list, tuple)) and len(alt) >= 2
    return False


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
        # Ponto único de decisão (ADR-013): cobre high_risk, destructive,
        # blocked e a escalação por risk_level==high — read-only nunca exige.
        # F7 P6: a expansão declarativa que funde corpos (combine-DENTRO)
        # também exige aprovação no PLANO (card disclosa antes de executar).
        requires_approval = _requires_approval(
            step.tool_name, step.risk_level
        ) or _declarative_combines(step)
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
