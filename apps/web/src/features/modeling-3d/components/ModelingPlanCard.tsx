import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Box,
  CheckCircle2,
  Loader2,
  Pencil,
  Plus,
  RotateCcw,
  Trash2,
  X,
  XCircle
} from "lucide-react";
import { useId, useMemo, useState } from "react";

import { Badge } from "../../../components/ui/Badge";
import { cn } from "../../../lib/utils";
import type { ModelingPlan, ModelingPlanEdit, ModelingPlanStep, ModelingRiskLevel } from "../types";

interface DraftStep {
  id: string | null;
  title: string;
  tool_name: string;
  risk_level: ModelingRiskLevel;
  inputText: string;
}

function toDraftSteps(steps: ModelingPlanStep[]): DraftStep[] {
  return steps.map((step) => ({
    id: step.id,
    title: step.title,
    tool_name: step.tool_name,
    risk_level: step.risk_level,
    inputText: JSON.stringify(step.input_json ?? {}, null, 2)
  }));
}

const CARD_BUTTON_BASE =
  "inline-flex h-7 items-center justify-center gap-1 rounded-md border px-2.5 text-[11px] font-medium transition disabled:cursor-not-allowed disabled:opacity-50";

const CARD_BUTTON_VARIANTS = {
  // Ação primária do fluxo 3D usa amethyst (cor secundária do bounded context).
  primary:
    "border-[color-mix(in_srgb,var(--amethyst)_50%,transparent)] bg-[color-mix(in_srgb,var(--amethyst)_16%,transparent)] text-forge-amethyst hover:bg-[color-mix(in_srgb,var(--amethyst)_24%,transparent)]",
  ghost: "border-forge-line bg-transparent text-forge-text hover:bg-forge-hover",
  danger:
    "border-forge-red/60 bg-[color-mix(in_srgb,var(--err)_14%,transparent)] text-forge-red hover:bg-[color-mix(in_srgb,var(--err)_22%,transparent)]"
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
  /** P4: edita o plano antes da aprovação (etapas/rationale). */
  onEditPlan?: (payload: ModelingPlanEdit) => Promise<void> | void;
  /** ``true`` while a network call started by this card is in flight. */
  isBusy?: boolean;
}

const RISK_BADGE_CLASS: Record<ModelingRiskLevel, string> = {
  low: "bg-[color-mix(in_srgb,var(--ok)_12%,transparent)] text-forge-green border-forge-green/40",
  medium: "bg-[color-mix(in_srgb,var(--ember)_12%,transparent)] text-forge-amber border-forge-amber/40",
  high: "bg-[color-mix(in_srgb,var(--err)_12%,transparent)] text-forge-red border-forge-red/60"
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
  return steps.filter((step) => step.risk_level === "high" || step.approval_required === true);
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
  onEditPlan,
  isBusy = false
}: ModelingPlanCardProps) {
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [editing, setEditing] = useState(false);
  const [draftSteps, setDraftSteps] = useState<DraftStep[]>([]);
  const [editError, setEditError] = useState<string | null>(null);
  const rejectInputId = useId();
  const highRisk = useMemo(() => highRiskSteps(plan.steps), [plan.steps]);
  const summary = (plan.rationale || plan.prompt || "").trim();
  const showApprovalButtons = isApprovable(plan) && !!(onApprove || onReject || onEditPlan);
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

  function startEditing() {
    setDraftSteps(toDraftSteps(plan.steps));
    setEditError(null);
    setEditing(true);
  }

  function updateDraft(index: number, patch: Partial<DraftStep>) {
    setDraftSteps((current) => current.map((step, i) => (i === index ? { ...step, ...patch } : step)));
  }

  function moveDraft(index: number, delta: number) {
    setDraftSteps((current) => {
      const target = index + delta;
      if (target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function removeDraft(index: number) {
    setDraftSteps((current) => current.filter((_, i) => i !== index));
  }

  function addDraft() {
    setDraftSteps((current) => [
      ...current,
      { id: null, title: "Nova etapa", tool_name: "", risk_level: "low", inputText: "{}" }
    ]);
  }

  async function handleSaveEdit() {
    if (!onEditPlan || isBusy) return;
    if (draftSteps.length === 0) {
      setEditError("O plano precisa de ao menos uma etapa.");
      return;
    }
    const steps = [];
    for (const [index, draft] of draftSteps.entries()) {
      if (!draft.tool_name.trim()) {
        setEditError(`Etapa ${index + 1}: informe o tool_name.`);
        return;
      }
      let inputJson: Record<string, unknown>;
      try {
        inputJson = draft.inputText.trim() ? JSON.parse(draft.inputText) : {};
      } catch {
        setEditError(`Etapa ${index + 1}: JSON inválido no campo de argumentos.`);
        return;
      }
      steps.push({
        id: draft.id,
        title: draft.title.trim() || `Etapa ${index + 1}`,
        tool_name: draft.tool_name.trim(),
        risk_level: draft.risk_level,
        input_json: inputJson
      });
    }
    setEditError(null);
    await onEditPlan({ steps });
    setEditing(false);
  }

  return (
    <section
      data-testid="modeling-plan-card"
      className="mt-3 rounded-md border border-[color-mix(in_srgb,var(--amethyst)_28%,transparent)] bg-[color-mix(in_srgb,var(--amethyst)_4%,var(--bg-card))] p-3 text-xs shadow-[0_12px_32px_-20px_var(--amethyst-glow)]"
      aria-label="Plano 3D MCP"
    >
      <header className="flex flex-col justify-between gap-2 md:flex-row md:items-start">
        <div>
          <div className="flex items-center gap-2 font-semibold text-forge-text">
            <span
              aria-hidden
              className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-white"
              style={{
                background:
                  "linear-gradient(155deg, var(--amethyst), color-mix(in srgb, var(--amethyst) 40%, var(--bg-ink)))"
              }}
            >
              <Box size={14} />
            </span>
            Plano 3D MCP
          </div>
          {summary && <p className="mt-1 line-clamp-3 text-forge-muted">{summary}</p>}
        </div>
        <div className="flex flex-wrap gap-1">
          <Badge>{plan.software_choice}</Badge>
          <Badge>{statusLabel(plan.status)}</Badge>
          {plan.planner_source && (
            <span
              // Vermelho quando o planner caiu em fallback heurístico — o
              // bug "uma bola virou retângulo" era invisível porque esse
              // sinal não aparecia. Tooltip nativo mostra a razão.
              className={
                plan.planner_source === "heuristic"
                  ? "inline-flex items-center rounded-full border border-forge-red/60 bg-[color-mix(in_srgb,var(--err)_12%,transparent)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-forge-red"
                  : "inline-flex items-center rounded-full border border-forge-line bg-forge-chip px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-forge-muted"
              }
              title={
                plan.planner_source === "heuristic" && plan.fallback_reason
                  ? `Fallback heurístico ativado.\nMotivo: ${plan.fallback_reason}`
                  : undefined
              }
            >
              {plan.planner_source === "llm" ? "planner: IA" : "planner: fallback"}
            </span>
          )}
          {plan.kind === "edit" && <Badge>edição</Badge>}
        </div>
      </header>

      {highRisk.length > 0 && (
        <div
          role="status"
          className="mt-3 flex items-start gap-2 rounded-sm border border-forge-amber/70 bg-[color-mix(in_srgb,var(--ember)_12%,transparent)] px-2.5 py-2 text-forge-amber"
        >
          <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden />
          <p className="leading-snug">
            <strong>{highRisk.length} etapa(s) high-risk</strong> nesse plano — aprovar autoriza todas, incluindo
            deleções e operações irreversíveis.
          </p>
        </div>
      )}

      <ol className="mt-3 space-y-1">
        {plan.steps.slice(0, 5).map((step) => (
          <li key={step.id} className="rounded border border-forge-line bg-forge-ink-deep px-2 py-1.5">
            <div className="flex items-center justify-between gap-2">
              <span className="line-clamp-1 font-medium">
                {step.seq}. {step.title}
              </span>
              <span
                className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] ${RISK_BADGE_CLASS[step.risk_level]}`}
              >
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

      {editing && (
        <div
          className="mt-3 rounded border border-[color-mix(in_srgb,var(--amethyst)_40%,transparent)] bg-forge-ink-deep p-2"
          data-testid="modeling-plan-editor"
        >
          <p className="mb-2 text-[11px] text-forge-muted">
            Edite as etapas (título, tool, risco e argumentos JSON). Reordene, remova ou adicione. Salvar mantém o plano
            aguardando sua aprovação.
          </p>
          <ol className="space-y-2">
            {draftSteps.map((draft, index) => (
              <li key={index} className="rounded border border-forge-line p-2">
                <div className="flex items-center gap-1">
                  <span className="text-forge-muted">{index + 1}.</span>
                  <input
                    aria-label={`Título da etapa ${index + 1}`}
                    className="flex-1 rounded border border-forge-line bg-forge-panel px-1.5 py-1 text-forge-text"
                    value={draft.title}
                    onChange={(e) => updateDraft(index, { title: e.target.value })}
                    disabled={isBusy}
                  />
                  <button
                    type="button"
                    className={cn(CARD_BUTTON_BASE, CARD_BUTTON_VARIANTS.ghost)}
                    onClick={() => moveDraft(index, -1)}
                    disabled={isBusy || index === 0}
                    aria-label={`Mover etapa ${index + 1} para cima`}
                  >
                    <ArrowUp size={12} aria-hidden />
                  </button>
                  <button
                    type="button"
                    className={cn(CARD_BUTTON_BASE, CARD_BUTTON_VARIANTS.ghost)}
                    onClick={() => moveDraft(index, 1)}
                    disabled={isBusy || index === draftSteps.length - 1}
                    aria-label={`Mover etapa ${index + 1} para baixo`}
                  >
                    <ArrowDown size={12} aria-hidden />
                  </button>
                  <button
                    type="button"
                    className={cn(CARD_BUTTON_BASE, CARD_BUTTON_VARIANTS.danger)}
                    onClick={() => removeDraft(index)}
                    disabled={isBusy}
                    aria-label={`Remover etapa ${index + 1}`}
                  >
                    <Trash2 size={12} aria-hidden />
                  </button>
                </div>
                <div className="mt-1 flex gap-1">
                  <input
                    aria-label={`Tool da etapa ${index + 1}`}
                    className="flex-1 rounded border border-forge-line bg-forge-panel px-1.5 py-1 font-mono text-[11px] text-forge-text"
                    value={draft.tool_name}
                    onChange={(e) => updateDraft(index, { tool_name: e.target.value })}
                    placeholder="ex.: fusion.add_box"
                    disabled={isBusy}
                  />
                  <select
                    aria-label={`Risco da etapa ${index + 1}`}
                    className="rounded border border-forge-line bg-forge-panel px-1 py-1 text-forge-text"
                    value={draft.risk_level}
                    onChange={(e) => updateDraft(index, { risk_level: e.target.value as ModelingRiskLevel })}
                    disabled={isBusy}
                  >
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                  </select>
                </div>
                <textarea
                  aria-label={`Argumentos JSON da etapa ${index + 1}`}
                  className="mt-1 w-full resize-y rounded border border-forge-line bg-forge-panel p-1.5 font-mono text-[11px] text-forge-text"
                  rows={2}
                  value={draft.inputText}
                  onChange={(e) => updateDraft(index, { inputText: e.target.value })}
                  disabled={isBusy}
                />
              </li>
            ))}
          </ol>
          {editError && (
            <p className="mt-2 text-forge-red" data-testid="modeling-plan-edit-error">
              {editError}
            </p>
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              className={cn(CARD_BUTTON_BASE, CARD_BUTTON_VARIANTS.ghost)}
              onClick={addDraft}
              disabled={isBusy}
            >
              <Plus size={12} aria-hidden /> Adicionar etapa
            </button>
            <button
              type="button"
              className={cn(CARD_BUTTON_BASE, CARD_BUTTON_VARIANTS.primary)}
              onClick={handleSaveEdit}
              disabled={isBusy}
              data-testid="modeling-plan-edit-save"
            >
              Salvar edição
            </button>
            <button
              type="button"
              className={cn(CARD_BUTTON_BASE, CARD_BUTTON_VARIANTS.ghost)}
              onClick={() => {
                setEditing(false);
                setEditError(null);
              }}
              disabled={isBusy}
            >
              <X size={12} aria-hidden /> Cancelar
            </button>
          </div>
        </div>
      )}

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
            {onEditPlan && !editing && (
              <button
                type="button"
                className={cn(CARD_BUTTON_BASE, CARD_BUTTON_VARIANTS.ghost)}
                onClick={startEditing}
                disabled={isBusy}
                data-testid="modeling-plan-edit-toggle"
              >
                <Pencil size={12} aria-hidden /> Editar plano
              </button>
            )}
          </div>
          {showRejectForm && (
            <div className="rounded border border-forge-red/40 bg-[color-mix(in_srgb,var(--err)_10%,transparent)] p-2">
              <label htmlFor={rejectInputId} className="block text-[11px] text-forge-muted">
                Motivo da rejeição (obrigatório):
              </label>
              <textarea
                id={rejectInputId}
                value={rejectReason}
                onChange={(event) => setRejectReason(event.target.value)}
                rows={2}
                disabled={isBusy}
                className="mt-1 w-full resize-y rounded border border-forge-line bg-forge-ink-deep p-1.5 text-forge-text"
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
            Aprovação acontece só pelos botões acima — texto livre no chat não executa o plano (ADR-013).
          </p>
        </div>
      )}

      {showExecutingBlock && (
        <div className="mt-3 flex items-center gap-2 rounded border border-forge-line bg-forge-ink-deep px-2 py-2 text-forge-muted">
          <Loader2 size={14} className="animate-spin text-forge-amethyst" aria-hidden />
          <span>Execução em andamento — acompanhe os passos acima.</span>
        </div>
      )}

      {showCompletedBlock && (
        <div className="mt-3 flex items-center gap-2 rounded border border-forge-green/40 bg-[color-mix(in_srgb,var(--ok)_10%,transparent)] px-2 py-2 text-forge-green">
          <CheckCircle2 size={14} aria-hidden />
          <span>Plano executado. Próximas mensagens viram edições no modelo.</span>
        </div>
      )}

      {showFailedBlock && (
        <div className="mt-3 rounded border border-forge-red/50 bg-[color-mix(in_srgb,var(--err)_10%,transparent)] p-2 text-forge-red">
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
        <p className="mt-3 text-forge-muted">Plano rejeitado. O agente vai retomar a descoberta na próxima mensagem.</p>
      )}
    </section>
  );
}
