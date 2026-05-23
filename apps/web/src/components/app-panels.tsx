import { Check, Database, FileText, Library, X } from "lucide-react";
import type { ReactNode } from "react";

import { platformFileLabel } from "../features/files/file-domain";
import type { PendingDuplicateFile } from "../features/files/file-domain";
import { formatBytes } from "../shared/utils/common";
import { Button } from "./ui/Button";

export function DuplicateFileModal({
  pending,
  onUseExisting,
  onSendCopy,
  onCancel
}: {
  pending: PendingDuplicateFile;
  onUseExisting: () => void;
  onSendCopy: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <div className="w-full max-w-lg rounded-md border border-forge-line bg-forge-panel p-4 shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-forge-line pb-3">
          <div>
            <p className="text-xs uppercase text-forge-muted">Arquivo duplicado</p>
            <h3 className="mt-1 text-lg font-semibold">Já existe um arquivo igual na biblioteca</h3>
          </div>
          <Button className="h-8 w-8 px-0" onClick={onCancel} aria-label="Fechar" title="Fechar">
            <X size={16} />
          </Button>
        </div>
        <div className="mt-4 grid gap-3 text-sm md:grid-cols-2">
          <div className="rounded-md border border-forge-line bg-forge-ink-deep p-3">
            <p className="text-xs uppercase text-forge-muted">Novo envio</p>
            <p className="mt-2 truncate font-medium">{pending.file.name}</p>
            <p className="mt-1 text-xs text-forge-muted">{formatBytes(pending.file.size)}</p>
          </div>
          <div className="rounded-md border border-forge-line bg-forge-ink-deep p-3">
            <p className="text-xs uppercase text-forge-muted">Existente</p>
            <p className="mt-2 truncate font-medium">{platformFileLabel(pending.duplicate)}</p>
            <p className="mt-1 text-xs text-forge-muted">
              {formatBytes(pending.duplicate.size_bytes)} · {pending.duplicate.source}
            </p>
          </div>
        </div>
        <p className="mt-4 text-sm leading-6 text-forge-muted">
          Você pode reaproveitar o arquivo existente ou enviar uma cópia. Se enviar mesmo assim, o backend salva com
          contador, como <span className="text-forge-text">arquivo (1).ext</span>.
        </p>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:justify-end">
          <Button className="h-9" onClick={onCancel}>
            Cancelar
          </Button>
          <Button className="h-9" onClick={onSendCopy}>
            Enviar cópia
          </Button>
          <Button className="h-9 border-forge-amber text-forge-amber" onClick={onUseExisting}>
            Usar existente
          </Button>
        </div>
      </div>
    </div>
  );
}

export function ContextChip({ label, value, dot = false }: { label: string; value: string; dot?: boolean }) {
  return (
    <div className="inline-flex min-h-8 items-center gap-2 rounded-md border border-forge-line-soft bg-forge-ink-deep px-2 text-xs">
      {dot && (
        <span
          aria-hidden
          className="h-1.5 w-1.5 shrink-0 rounded-full bg-forge-amber"
          style={{ boxShadow: "0 0 6px var(--ember-glow)" }}
        />
      )}
      <span className="uppercase text-forge-muted">{label}</span>
      <span className="max-w-60 truncate text-forge-text">{value}</span>
    </div>
  );
}

export function ExecutionMenuItem({
  label,
  active,
  disabled = false,
  title,
  onClick
}: {
  label: string;
  active: boolean;
  disabled?: boolean;
  title?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={[
        "flex h-8 w-full items-center justify-between rounded px-2 text-xs transition",
        disabled
          ? "cursor-not-allowed text-forge-muted/40"
          : "text-forge-muted hover:bg-forge-hover hover:text-forge-text"
      ].join(" ")}
      disabled={disabled}
      title={title}
      onClick={onClick}
    >
      <span>{label}</span>
      {active && <Check size={13} className="text-forge-amber" />}
    </button>
  );
}

export function SearchIcon() {
  return <Library size={18} />;
}

export function PanelTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2 pt-1">
      <span className="text-forge-amber [&_svg]:h-3.5 [&_svg]:w-3.5">{icon}</span>
      <span className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-forge-text-soft">{title}</span>
    </div>
  );
}

export function InfoRow({ label, value }: { label: string; value: string }) {
  const icon = label === "Documentos" ? <FileText size={14} /> : label === "Vetores" ? <Database size={14} /> : null;
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="flex items-center gap-2 text-forge-muted">
        {icon}
        {label}
      </span>
      <span className="min-w-0 truncate text-right">{value}</span>
    </div>
  );
}

export function EmptyPanel({ text }: { text: string }) {
  return <div className="rounded-md border border-dashed border-forge-line p-4 text-sm text-forge-muted">{text}</div>;
}
