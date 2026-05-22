import { CheckCircle2, Pencil, XCircle } from "lucide-react";

import { Badge } from "../../../components/ui/Badge";
import type { ModelingPlan } from "../types";

/**
 * Compact card for mini-plans (``kind="edit"``) shown in the editing stage.
 *
 * Per ADR-013 the orchestrator auto-approves edit plans whose steps are
 * all non-high-risk and runs them immediately. The user sees this card
 * as a *report* of what just happened — no buttons, no approval gate,
 * only the final state plus the list of executed tool calls.
 *
 * When an edit plan does contain a high-risk step the orchestrator
 * surfaces it through :class:`ModelingPlanCard` instead (which keeps
 * the inline approval UI). This component intentionally has no
 * approval/reject paths.
 */
export interface ModelingEditCardProps {
  plan: ModelingPlan;
}

function summaryText(plan: ModelingPlan): string {
  const trimmed = (plan.rationale || plan.prompt || "").trim();
  if (!trimmed) return "Edição executada no modelo 3D.";
  return trimmed;
}

function iconFor(plan: ModelingPlan) {
  if (plan.status === "failed") {
    return <XCircle size={13} className="text-forge-red" aria-hidden />;
  }
  if (plan.status === "completed") {
    return <CheckCircle2 size={13} className="text-emerald-300" aria-hidden />;
  }
  return <Pencil size={13} className="text-forge-amber" aria-hidden />;
}

export function ModelingEditCard({ plan }: ModelingEditCardProps) {
  const summary = summaryText(plan);
  const executedCount = plan.steps.filter((step) => step.status === "completed").length;
  const failedCount = plan.steps.filter((step) => step.status === "failed").length;

  return (
    <section
      data-testid="modeling-edit-card"
      className="mt-2 rounded-md border border-forge-line bg-[#0e0f0e] px-2.5 py-2 text-[11px]"
      aria-label="Edição de plano 3D"
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 font-medium text-forge-text">
          {iconFor(plan)}
          Edição executada
        </div>
        <div className="flex flex-wrap gap-1">
          <Badge>{plan.software_choice}</Badge>
          <Badge>{plan.status}</Badge>
          <Badge>edição</Badge>
        </div>
      </header>
      <p className="mt-1 line-clamp-2 text-forge-muted">{summary}</p>
      <p className="mt-1 text-forge-muted">
        {executedCount} etapa(s) executada(s)
        {failedCount > 0 ? ` · ${failedCount} com falha` : ""} · sem aprovação adicional (allowlist segura).
      </p>
    </section>
  );
}
