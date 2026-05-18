import { useCallback, useEffect, useId, useRef } from "react";
import { X } from "lucide-react";

import { formatDurationMs, formatRiskPercentage, formatTimestamp, riskSeverityClass } from "../format";
import { useModeling3dDiagnostics } from "../hooks";

type ModelingDiagnosticsModalProps = {
  open: boolean;
  planId?: string | null;
  projectId?: string | null;
  onClose: () => void;
};

export function ModelingDiagnosticsModal({ open, planId, projectId, onClose }: ModelingDiagnosticsModalProps) {
  const diagnosticsQuery = useModeling3dDiagnostics(planId, projectId);
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return undefined;
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    document.body.classList.add("overflow-hidden");
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
      <div className="flex max-h-[88vh] w-full max-w-3xl flex-col rounded-lg border border-forge-line bg-[#111312] shadow-xl">
        <div className="flex items-start justify-between gap-3 border-b border-forge-line p-4">
          <div>
            <p className="text-xs uppercase text-forge-muted">Diagnóstico MCP</p>
            <h3 id={titleId} className="text-lg font-semibold">Modelagem 3D</h3>
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
          {diagnosticsQuery.isLoading && <p className="text-sm text-forge-muted">Carregando diagnóstico...</p>}
          {diagnosticsQuery.isError && <p className="text-sm text-forge-red">Falha ao carregar diagnóstico MCP 3D.</p>}
          {diagnostics && (
            <>
              <section className="grid gap-2">
                <h4 className="text-sm font-semibold">Adapters</h4>
                {diagnostics.capabilities.adapters.map((adapter) => (
                  <div key={adapter.software} className="rounded-md border border-forge-line bg-[#171716] p-3 text-sm">
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
                  <div key={call.id} className="rounded-md border border-forge-line bg-[#171716] p-3 text-xs">
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
                  <div key={report.id} className="rounded-md border border-forge-line bg-[#171716] p-3 text-xs">
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
                  <div key={version.id} className="rounded-md border border-forge-line bg-[#171716] p-3 text-xs">
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
