import { AlertTriangle, Box, CheckCircle2, Loader2, RotateCcw, X, XCircle } from "lucide-react";
import { useId, useMemo, useState } from "react";

import { Badge } from "../../../components/ui/Badge";
import { cn } from "../../../lib/utils";
import type { ModelingPlan, ModelingPlanStep, ModelingRiskLevel } from "../types";

const CARD_BUTTON_BASE =
  "inline-flex h-7 items-center justify-center gap-1 rounded-md border px-2.5 text-[11px] font-medium transition disabled:cursor-not-allowed disabled:opacity-50";

const CARD_BUTTON_VARIANTS = {
  primary:
    "border-forge-amber/60 bg-[#241d12] text-forge-amber hover:bg-[#2e2417]",
  ghost: "border-forge-line bg-transparent text-forge-text hover:bg-[#1a1d20]",
  danger: "border-forge-red/60 bg-[#2a1414] text-forge-red hover:bg-[#3a1818]"
} as const;

/**
 * In-chat card that drives the ADR-013 chat-first approval flow.
 *
 * The card lives next to each assistant message that proposed a plan
 * (``kind="primary"``) or a high-risk edit waiting for approval. It
 * surfaces:
 *
 * * a prose summary (rationale falls back to the original prompt),
 * * a banner whenever any step is high-risk so the user sees the warn
 *   before clicking "Aprovar",
 * * the step list with risk-level pills,
 * * "Aprovar" / "Rejeitar" buttons inline (textual responses do
 *   **not** count — see ADR-013), with an optional reason field on
 *   rejection,
 * * a busy/executing state while the orchestrator is mid-execution,
 * * a failed state offering "Tentar novamente" and "Revisar plano"
 *   when the executor reported errors.
 *
 * The component is purely presentational: the parent (chat-stream
 * handler / orchestrator) provides the callbacks. We never call the
 * approval endpoint from here directly.
 */
export interface ModelingPlanCardProps {
  plan: ModelingPlan;
  /** Approve the plan. ``reason`` is currently always empty for approval but
   *  kept symmetric with reject. */
  onApprove?: (reason?: string) => Promise<void> | void;
  onReject?: (reason: string) => Promise<void> | void;
  /** Re-execute a previously-failed plan (Onda 4.6). */
  onRetry?: () => Promise<void> | void;
  /** Reopen the plan for editing/discovery (Onda 4.6 — "Revisar plano"). */
  onRevise?: () => Promise<void> | void;
  /** ``true`` while a network call started by this card is in flight. */
  isBusy?: boolean;
}

const RISK_BADGE_CLASS: Record<ModelingRiskLevel, string> = {
  low: "bg-[#1a2417] text-emerald-300 border-emerald-500/40",
  medium: "bg-[#241d12] text-forge-amber border-forge-amber/40",
  high: "bg-[#2a1414] text-forge-red border-forge-red/60"
};

const STATUS_LABEL: Record<string, string> = {
  draft: "rascunho",
  waiting_approval: "aguardando aprovação",
  approved: "aprovado",
  running: "executando",
  completed: "concluído",
  rejected: "rejeitado",
  failed: "falhou",
  pending: "pendente"
};

function statusLabel(status: string | undefined | null): string {
  if (!status) return "—";
  return STATUS_LABEL[status] ?? status;
}

function highRiskSteps(steps: ModelingPlanStep[]): ModelingPlanStep[] {
  return steps.filter(
    (step) => step.risk_level === "high" || step.approval_required === true
  );
}

function isApprovable(plan: ModelingPlan): boolean {
  return plan.status === "waiting_approval" || plan.status === "draft";
}

function isExecuting(plan: ModelingPlan): boolean {
  return plan.status === "running";
}

function isCompleted(plan: ModelingPlan): boolean {
  return plan.status === "completed";
}

function isFailed(plan: ModelingPlan): boolean {
  return plan.status === "failed";
}

function isRejected(plan: ModelingPlan): boolean {
  return plan.status === "rejected";
}

export function ModelingPlanCard({
  plan,
  onApprove,
  onReject,
  onRetry,
  onRevise,
  isBusy = false
}: ModelingPlanCardProps) {
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const rejectInputId = useId();
  const highRisk = useMemo(() => highRiskSteps(plan.steps), [plan.steps]);
  const summary = (plan.rationale || plan.prompt || "").trim();
  const showApprovalButtons = isApprovable(plan) && !!(onApprove || onReject);
  const showExecutingBlock = isExecuting(plan);
  const showCompletedBlock = isCompleted(plan);
  const showFailedBlock = isFailed(plan);
  const showRejectedBlock = isRejected(plan);

  async function handleApprove() {
    if (!onApprove || isBusy) return;
    await onApprove();
  }

  async function handleConfirmReject() {
    if (!onReject || isBusy) return;
    const reason = rejectReason.trim();
    if (!reason) return;
    await onReject(reason);
    setShowRejectForm(false);
    setRejectReason("");
  }

  return (
    <section
      data-testid="modeling-plan-card"
      className="mt-3 rounded-md border border-forge-amber/40 bg-[#18150f] p-3 text-xs"
      aria-label="Plano 3D MCP"
    >
      <header className="flex flex-col justify-between gap-2 md:flex-row md:items-start">
        <div>
          <div className="flex items-center gap-2 font-semibold text-forge-text">
            <Box size={15} className="text-forge-amber" aria-hidden />
            Plano 3D MCP
          </div>
          {summary && <p className="mt-1 line-clamp-3 text-forge-muted">{summary}</p>}
        </div>
        <div className="flex flex-wrap gap-1">
          <Badge>{plan.software_choice}</Badge>
          <Badge>{statusLabel(plan.status)}</Badge>
          {plan.planner_source && (
            <Badge>{plan.planner_source === "llm" ? "planner: IA" : "planner: heurístico"}</Badge>
          )}
          {plan.kind === "edit" && <Badge>edição</Badge>}
        </div>
      </header>

      {highRisk.length > 0 && (
        <div
          role="status"
          className="mt-3 flex items-start gap-2 rounded-sm border border-forge-amber/70 bg-[#2a2110] px-2.5 py-2 text-forge-amber"
        >
          <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden />
          <p className="leading-snug">
            <strong>{highRisk.length} etapa(s) high-risk</strong> nesse plano —
            aprovar autoriza todas, incluindo deleções e operações irreversíveis.
          </p>
        </div>
      )}

      <ol className="mt-3 space-y-1">
        {plan.steps.slice(0, 5).map((step) => (
          <li key={step.id} className="rounded border border-forge-line bg-[#0e0f0e] px-2 py-1.5">
            <div className="flex items-center justify-between gap-2">
              <span className="line-clamp-1 font-medium">
                {step.seq}. {step.title}
              </span>
              <span className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] ${RISK_BADGE_CLASS[step.risk_level]}`}>
                {step.risk_level}
              </span>
            </div>
            <p className="mt-1 line-clamp-1 text-forge-muted">
              {step.tool_name} · {statusLabel(step.status)}
              {step.approval_required ? " · aprovação inline" : " · auto"}
            </p>
          </li>
        ))}
        {plan.steps.length > 5 && (
          <li className="text-forge-muted">+ {plan.steps.length - 5} etapa(s) no plano completo.</li>
        )}
      </ol>

      {showApprovalButtons && (
        <div className="mt-3 flex flex-col gap-2">
          <div className="flex flex-wrap gap-2">
            {onApprove && (
              <button
                type="button"
                className={cn(CARD_BUTTON_BASE, CARD_BUTTON_VARIANTS.primary)}
                onClick={handleApprove}
                disabled={isBusy}
                data-testid="modeling-plan-approve"
              >
                Aprovar
              </button>
            )}
            {onReject && !showRejectForm && (
              <button
                type="button"
                className={cn(CARD_BUTTON_BASE, CARD_BUTTON_VARIANTS.ghost)}
                onClick={() => setShowRejectForm(true)}
                disabled={isBusy}
                data-testid="modeling-plan-reject-toggle"
              >
                Rejeitar
              </button>
            )}
          </div>
          {showRejectForm && (
            <div className="rounded border border-forge-red/40 bg-[#1a0f0f] p-2">
              <label htmlFor={rejectInputId} className="block text-[11px] text-forge-muted">
                Motivo da rejeição (obrigatório):
              </label>
              <textarea
                id={rejectInputId}
                value={rejectReason}
                onChange={(event) => setRejectReason(event.target.value)}
                rows={2}
                disabled={isBusy}
                className="mt-1 w-full resize-y rounded border border-forge-line bg-[#0e0f0e] p-1.5 text-forge-text"
                placeholder="Explique o que falta ou está errado para o agente voltar para descoberta."
                data-testid="modeling-plan-reject-reason"
              />
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  className={cn(CARD_BUTTON_BASE, CARD_BUTTON_VARIANTS.danger)}
                  onClick={handleConfirmReject}
                  disabled={isBusy || !rejectReason.trim()}
                  data-testid="modeling-plan-reject-confirm"
                >
                  Confirmar rejeição
                </button>
                <button
                  type="button"
                  className={cn(CARD_BUTTON_BASE, CARD_BUTTON_VARIANTS.ghost)}
                  onClick={() => {
                    setShowRejectForm(false);
                    setRejectReason("");
                  }}
                  disabled={isBusy}
                >
                  <X size={12} aria-hidden /> Cancelar
                </button>
              </div>
            </div>
          )}
          <p className="text-[11px] text-forge-muted">
            Aprovação acontece só pelos botões acima — texto livre no chat não
            executa o plano (ADR-013).
          </p>
        </div>
      )}

      {showExecutingBlock && (
        <div className="mt-3 flex items-center gap-2 rounded border border-forge-line bg-[#0e0f0e] px-2 py-2 text-forge-muted">
          <Loader2 size={14} className="animate-spin text-forge-amber" aria-hidden />
          <span>Execução em andamento — acompanhe os passos acima.</span>
        </div>
      )}

      {showCompletedBlock && (
        <div className="mt-3 flex items-center gap-2 rounded border border-emerald-500/40 bg-[#0f1a13] px-2 py-2 text-emerald-300">
          <CheckCircle2 size={14} aria-hidden />
          <span>Plano executado. Próximas mensagens viram edições no modelo.</span>
        </div>
      )}

      {showFailedBlock && (
        <div className="mt-3 rounded border border-forge-red/50 bg-[#1a0f0f] p-2 text-forge-red">
          <div className="flex items-center gap-2 font-medium">
            <XCircle size={14} aria-hidden />
            <span>Execução falhou em uma ou mais etapas.</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {onRetry && (
              <button
                type="button"
                className={cn(CARD_BUTTON_BASE, CARD_BUTTON_VARIANTS.ghost)}
                onClick={() => onRetry?.()}
                disabled={isBusy}
                data-testid="modeling-plan-retry"
              >
                <RotateCcw size={12} aria-hidden /> Tentar novamente
              </button>
            )}
            {onRevise && (
              <button
                type="button"
                className={cn(CARD_BUTTON_BASE, CARD_BUTTON_VARIANTS.ghost)}
                onClick={() => onRevise?.()}
                disabled={isBusy}
                data-testid="modeling-plan-revise"
              >
                Revisar plano
              </button>
            )}
          </div>
        </div>
      )}

      {showRejectedBlock && (
        <p className="mt-3 text-forge-muted">
          Plano rejeitado. O agente vai retomar a descoberta na próxima mensagem.
        </p>
      )}
    </section>
  );
}
