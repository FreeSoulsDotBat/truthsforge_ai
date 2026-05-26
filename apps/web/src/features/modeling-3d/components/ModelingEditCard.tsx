import { CheckCircle2, Pencil, Undo2, XCircle } from "lucide-react";
import { useState } from "react";

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
 *
 * T3.6: completed *fusion* edits that captured a pre-edit timeline
 * (``plan.rollback_marker != null``) expose a "Desfazer última edição"
 * button that reverts the model via ``POST /api/3d/plans/{id}/rollback``.
 */
export interface ModelingEditCardProps {
  plan: ModelingPlan;
  /** Disables the rollback button while another plan action is in flight. */
  isBusy?: boolean;
  /** T3.6: desfaz esta edição. Resolve ``true`` no sucesso (card mostra "desfeito"). */
  onRollback?: (planId: string) => Promise<boolean> | void;
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
    return <CheckCircle2 size={13} className="text-forge-green" aria-hidden />;
  }
  return <Pencil size={13} className="text-forge-amber" aria-hidden />;
}

export function ModelingEditCard({ plan, isBusy, onRollback }: ModelingEditCardProps) {
  const summary = summaryText(plan);
  const executedCount = plan.steps.filter((step) => step.status === "completed").length;
  const failedCount = plan.steps.filter((step) => step.status === "failed").length;

  const [pending, setPending] = useState(false);
  const [rolledBack, setRolledBack] = useState(false);
  // Edições concluídas E falhas podem ser desfeitas: uma edição que falhou no
  // meio já aplicou passos parciais (ex.: o 1º fillet entrou antes do 2º falhar),
  // então o rollback ao ponto pré-edição é justamente o que se quer.
  const canRollback =
    Boolean(onRollback) &&
    plan.kind === "edit" &&
    (plan.status === "completed" || plan.status === "failed") &&
    plan.rollback_marker != null;

  const handleRollback = async () => {
    if (!onRollback) return;
    setPending(true);
    try {
      const ok = await onRollback(plan.id);
      if (ok !== false) setRolledBack(true);
    } finally {
      setPending(false);
    }
  };

  return (
    <section
      data-testid="modeling-edit-card"
      className="mt-2 rounded-md border border-[color-mix(in_srgb,var(--ember)_28%,transparent)] bg-[color-mix(in_srgb,var(--ember)_4%,var(--bg-card))] px-2.5 py-2 text-[11px]"
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
      {rolledBack ? (
        <p className="mt-1.5 flex items-center gap-1 text-forge-muted" data-testid="modeling-edit-rolled-back">
          <Undo2 size={12} aria-hidden /> Edição desfeita.
        </p>
      ) : canRollback ? (
        <div className="mt-1.5">
          <button
            type="button"
            data-testid="modeling-edit-rollback"
            onClick={handleRollback}
            disabled={pending || isBusy}
            className="inline-flex h-6 items-center gap-1 rounded-sm border border-forge-line-soft bg-forge-panel px-2 text-[11px] text-forge-text transition-colors hover:bg-forge-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Undo2 size={12} aria-hidden />
            {pending ? "Desfazendo…" : "Desfazer última edição"}
          </button>
        </div>
      ) : null}
    </section>
  );
}
