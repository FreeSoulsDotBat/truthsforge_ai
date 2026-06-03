import { useCallback, useEffect, useId, useRef, useState } from "react";
import { X } from "lucide-react";

import { formatDurationMs, formatRiskPercentage, formatTimestamp, riskSeverityClass } from "../format";
import { useModeling3dDiagnostics, useModeling3dTrace, useRecordClientTrace } from "../hooks";
import type { ModelingTraceEvent } from "../../../types/api";

type ModelingDiagnosticsModalProps = {
  open: boolean;
  planId?: string | null;
  projectId?: string | null;
  traceId?: string | null;
  onClose: () => void;
};

function traceLevelClass(level: ModelingTraceEvent["level"]): string {
  switch (level) {
    case "error":
      return "text-forge-red";
    case "warn":
      return "text-forge-amber";
    case "debug":
      return "text-forge-muted";
    default:
      return "text-forge-text";
  }
}

function traceSourceLabel(source: ModelingTraceEvent["source"]): string {
  switch (source) {
    case "ui":
      return "UI";
    case "backend":
      return "Backend";
    case "mcp":
      return "MCP";
    case "fusion":
      return "Fusion";
    case "blender":
      return "Blender";
    default:
      return String(source).toUpperCase();
  }
}

export function ModelingDiagnosticsModal({ open, planId, projectId, traceId, onClose }: ModelingDiagnosticsModalProps) {
  const diagnosticsQuery = useModeling3dDiagnostics(planId, projectId);
  const traceQuery = useModeling3dTrace(planId, traceId, { enabled: open });
  const recordEvent = useRecordClientTrace(traceId, planId);
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  // Mantém os valores mais recentes para o effect de abertura sem precisar
  // listá-los nas deps (evita re-disparar focus/overflow/recordEvent a cada
  // mudança de planId/traceId/recordEvent).
  const openEffectRef = useRef({ recordEvent, planId, traceId });
  // Atualiza os valores mais recentes FORA do render: um effect sem deps roda
  // a cada commit. (eslint proíbe mutar ref.current durante o render.)
  useEffect(() => {
    openEffectRef.current = { recordEvent, planId, traceId };
  });

  // Estado local: filtros visuais aplicados aos trace events (no client).
  // Decisão: filtrar no cliente em vez de re-requisitar com querystring —
  // evita roundtrip e mantém estado UX quando alterna filtros rapidamente.
  const [traceLevelFilter, setTraceLevelFilter] = useState<Set<ModelingTraceEvent["level"]>>(
    new Set(["info", "warn", "error"])
  );

  useEffect(() => {
    if (!open) return undefined;
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    document.body.classList.add("overflow-hidden");
    // Registra evento UI no trace — abre confirma que o usuário viu o
    // diagnóstico (útil para correlacionar com tickets de bug). Usa os
    // valores via ref para registrar uma única vez por abertura, sem
    // re-disparar (e roubar foco) a cada mudança de planId/traceId.
    const { recordEvent: record, planId: pid, traceId: tid } = openEffectRef.current;
    record("ui.diagnostics_modal_opened", { planId: pid, traceId: tid });
    return () => {
      document.body.classList.remove("overflow-hidden");
      previouslyFocusedRef.current?.focus?.();
    };
  }, [open]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    },
    [onClose]
  );

  if (!open) return null;

  const diagnostics = diagnosticsQuery.data;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      onKeyDown={handleKeyDown}
    >
      <div className="flex max-h-[88vh] w-full max-w-3xl flex-col rounded-lg border border-forge-line bg-forge-elev shadow-[0_16px_36px_-20px_var(--amethyst-glow)]">
        <div className="flex items-start justify-between gap-3 border-b border-forge-line p-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-forge-amethyst">Diagnóstico MCP</p>
            <h3 id={titleId} className="mt-1 font-display text-lg uppercase tracking-[0.015em] text-forge-text">
              Modelagem 3D
            </h3>
            <p className="text-sm text-forge-muted">Adapters, tool calls, printability e artifacts do chat 3D.</p>
          </div>
          <button
            ref={closeRef}
            type="button"
            className="rounded-md border border-forge-line p-2 text-forge-muted hover:text-forge-text"
            onClick={onClose}
            aria-label="Fechar diagnóstico 3D"
          >
            <X size={16} />
          </button>
        </div>
        <div className="scrollbar-slim space-y-4 overflow-y-auto p-4">
          {/* Trace section first — é a mais útil pra debug de falhas */}
          {(traceId || planId) && (
            <section className="grid gap-2">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h4 className="text-sm font-semibold">Trace</h4>
                <div className="flex items-center gap-2 text-[10px] text-forge-muted">
                  {(["debug", "info", "warn", "error"] as const).map((lvl) => {
                    const active = traceLevelFilter.has(lvl);
                    return (
                      <button
                        key={lvl}
                        type="button"
                        onClick={() =>
                          setTraceLevelFilter((prev) => {
                            const next = new Set(prev);
                            if (next.has(lvl)) next.delete(lvl);
                            else next.add(lvl);
                            return next;
                          })
                        }
                        className={
                          active
                            ? "rounded-full border border-forge-line bg-forge-panel px-2 py-0.5 uppercase tracking-wide text-forge-text"
                            : "rounded-full border border-forge-line/30 px-2 py-0.5 uppercase tracking-wide text-forge-muted/60"
                        }
                      >
                        {lvl}
                      </button>
                    );
                  })}
                </div>
              </div>
              {traceId && (
                <p className="text-[10px] text-forge-muted">
                  <span className="font-mono">trace_id:</span>{" "}
                  <code
                    className="cursor-pointer rounded bg-forge-panel px-1 py-0.5 hover:text-forge-text"
                    onClick={() => navigator.clipboard?.writeText(traceId).catch(() => undefined)}
                    title="Copiar trace_id (correlaciona com docker logs do backend)"
                  >
                    {traceId}
                  </code>
                </p>
              )}
              {traceQuery.isLoading && <p className="text-xs text-forge-muted">Carregando trace...</p>}
              {traceQuery.isError && <p className="text-xs text-forge-red">Falha ao carregar trace.</p>}
              {traceQuery.data && traceQuery.data.length === 0 && (
                <p className="text-xs text-forge-muted">
                  Sem eventos de trace para este plano. (Observabilidade pode estar desativada — veja
                  TRUTHS_FORGE_MODELING_OBSERVABILITY_ENABLED.)
                </p>
              )}
              {traceQuery.data &&
                traceQuery.data
                  .filter((evt) => traceLevelFilter.has(evt.level))
                  .map((evt) => (
                    <details key={evt.id} className="rounded-md border border-forge-line bg-forge-panel p-2 text-xs">
                      <summary className="flex flex-wrap items-center justify-between gap-2 cursor-pointer">
                        <span className="flex items-center gap-2">
                          <span className="rounded bg-forge-ink-deep px-1.5 py-0.5 text-[10px] uppercase text-forge-muted">
                            {traceSourceLabel(evt.source)}
                          </span>
                          <span className={`font-medium ${traceLevelClass(evt.level)}`}>{evt.event_type}</span>
                          {evt.duration_ms != null && (
                            <span className="text-forge-muted">· {formatDurationMs(evt.duration_ms)}</span>
                          )}
                        </span>
                        <span className="text-forge-muted">{formatTimestamp(evt.created_at)}</span>
                      </summary>
                      {evt.message && <p className="mt-2 text-forge-muted">{evt.message}</p>}
                      {evt.payload && Object.keys(evt.payload).length > 0 && (
                        <pre className="mt-2 max-h-48 overflow-auto rounded bg-forge-ink-deep p-2 text-[10px] text-forge-muted">
                          {JSON.stringify(evt.payload, null, 2)}
                        </pre>
                      )}
                    </details>
                  ))}
            </section>
          )}
          {diagnosticsQuery.isLoading && <p className="text-sm text-forge-muted">Carregando diagnóstico...</p>}
          {diagnosticsQuery.isError && <p className="text-sm text-forge-red">Falha ao carregar diagnóstico MCP 3D.</p>}
          {diagnostics && (
            <>
              <section className="grid gap-2">
                <h4 className="text-sm font-semibold">Adapters</h4>
                {diagnostics.capabilities.adapters.map((adapter) => (
                  <div
                    key={adapter.software}
                    className="rounded-md border border-forge-line bg-forge-panel p-3 text-sm"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium">{adapter.software}</span>
                      <span className="rounded-full border border-forge-line px-2 py-0.5 text-xs text-forge-muted">
                        {adapter.connected ? "conectado" : adapter.status}
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-forge-muted">
                      {adapter.transport} · {adapter.detail}
                    </p>
                  </div>
                ))}
              </section>
              <section className="grid gap-2">
                <h4 className="text-sm font-semibold">Tool calls recentes</h4>
                {diagnostics.toolCalls.slice(0, 8).map((call) => (
                  <div key={call.id} className="rounded-md border border-forge-line bg-forge-panel p-3 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-sm">{call.tool_name}</span>
                      <span className={call.status === "ok" ? "text-forge-green" : "text-forge-red"}>
                        {call.status}
                      </span>
                    </div>
                    <p className="mt-1 text-forge-muted">
                      {call.software} · {call.transport} · {formatDurationMs(call.duration_ms)} ·{" "}
                      {formatTimestamp(call.created_at)}
                    </p>
                  </div>
                ))}
                {!diagnostics.toolCalls.length && (
                  <p className="text-xs text-forge-muted">Sem tool calls para este plano.</p>
                )}
              </section>
              <section className="grid gap-2">
                <h4 className="text-sm font-semibold">Printability</h4>
                {diagnostics.printabilityReports.slice(0, 4).map((report) => (
                  <div key={report.id} className="rounded-md border border-forge-line bg-forge-panel p-3 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span>{report.summary}</span>
                      <span className={riskSeverityClass(report.risk_score)}>
                        risco {formatRiskPercentage(report.risk_score)}
                      </span>
                    </div>
                  </div>
                ))}
                {!diagnostics.printabilityReports.length && (
                  <p className="text-xs text-forge-muted">Sem relatórios de printability para este plano.</p>
                )}
              </section>
              <section className="grid gap-2">
                <h4 className="text-sm font-semibold">Versões/exportações</h4>
                {diagnostics.modelVersions.slice(0, 6).map((version) => (
                  <div key={version.id} className="rounded-md border border-forge-line bg-forge-panel p-3 text-xs">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span>{version.label}</span>
                      <span>{version.export_format ?? version.software}</span>
                    </div>
                    <p className="mt-1 text-forge-muted">
                      {version.file_ids.length} arquivo(s) · {formatTimestamp(version.created_at)}
                    </p>
                  </div>
                ))}
                {!diagnostics.modelVersions.length && (
                  <p className="text-xs text-forge-muted">Sem exports versionados.</p>
                )}
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
