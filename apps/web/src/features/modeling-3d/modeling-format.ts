/**
 * Formatting helpers shared by the 3D dashboard panels.
 *
 * Kept as pure functions so they can be unit-tested without rendering the
 * whole modeling dashboard. Numeric inputs come straight from the backend
 * payloads (see ``ModelingToolCall`` / ``ModelingPrintabilityReport`` in
 * ``types/api.ts``); ``null``/``undefined`` collapse to a dash placeholder.
 */

export const PLACEHOLDER = "—";

// Rótulos PT-BR para status de plano/etapa (produto é PT-BR — AGENTS.md).
// Fonte única compartilhada por ModelingPlanCard e ModelingEditCard.
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

export function statusLabel(status: string | undefined | null): string {
  if (!status) return PLACEHOLDER;
  return STATUS_LABEL[status] ?? status;
}

export function formatDurationMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return PLACEHOLDER;
  if (ms < 0) return PLACEHOLDER;
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) {
    const seconds = ms / 1000;
    // Drop the decimal when the value is exact enough to read at a glance.
    return seconds >= 10 ? `${Math.round(seconds)} s` : `${seconds.toFixed(1)} s`;
  }
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return seconds === 0 ? `${minutes} min` : `${minutes} min ${seconds} s`;
}

export function formatConfidencePercentage(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) return PLACEHOLDER;
  const clamped = Math.max(0, Math.min(1, score));
  return `${Math.round(clamped * 100)}%`;
}

export function formatRiskPercentage(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) return PLACEHOLDER;
  const clamped = Math.max(0, Math.min(1, score));
  return `${Math.round(clamped * 100)}%`;
}

export type RiskSeverity = "ok" | "info" | "warning" | "danger";

export function riskSeverity(score: number | null | undefined): RiskSeverity {
  if (score === null || score === undefined || Number.isNaN(score)) return "ok";
  if (score <= 0) return "ok";
  if (score < 0.2) return "info";
  if (score < 0.5) return "warning";
  return "danger";
}

const RISK_SEVERITY_CLASS: Record<RiskSeverity, string> = {
  ok: "text-forge-muted",
  info: "text-forge-text",
  warning: "text-forge-amber",
  danger: "text-forge-red"
};

export function riskSeverityClass(score: number | null | undefined): string {
  return RISK_SEVERITY_CLASS[riskSeverity(score)];
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return PLACEHOLDER;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return PLACEHOLDER;
  return date.toLocaleString("pt-BR", { hour12: false });
}

/**
 * Truncate a long message safely for badges/tooltips without breaking words mid-grapheme.
 */
export function truncate(value: string | null | undefined, limit = 120): string {
  if (!value) return "";
  if (value.length <= limit) return value;
  return `${value.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
}
