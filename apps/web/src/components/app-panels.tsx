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
      <div className="w-full max-w-lg rounded-md border border-forge-line bg-[#141615] p-4 shadow-2xl">
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
          <div className="rounded-md border border-forge-line bg-[#0e0f0e] p-3">
            <p className="text-xs uppercase text-forge-muted">Novo envio</p>
            <p className="mt-2 truncate font-medium">{pending.file.name}</p>
            <p className="mt-1 text-xs text-forge-muted">{formatBytes(pending.file.size)}</p>
          </div>
          <div className="rounded-md border border-forge-line bg-[#0e0f0e] p-3">
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

export function DashboardNavButton({
  active,
  icon,
  label,
  onClick
}: {
  active: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={[
        "flex h-9 items-center justify-start gap-2 rounded px-3 text-sm transition",
        active ? "bg-[#24211b] text-forge-text" : "text-forge-muted hover:bg-[#181b1e] hover:text-forge-text"
      ].join(" ")}
      onClick={onClick}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

export function ContextChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="inline-flex min-h-8 items-center gap-2 rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-xs">
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
          : "text-forge-muted hover:bg-[#1b1f22] hover:text-forge-text"
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

export function PanelStack({ children }: { children: ReactNode }) {
  return (
    <div className="scrollbar-slim flex max-h-[calc(100vh-112px)] flex-col gap-4 overflow-y-auto pb-8 pr-1">
      {children}
    </div>
  );
}

export function PanelButton({
  active,
  icon,
  label,
  onClick
}: {
  active: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={[
        "flex h-9 items-center justify-center rounded border text-forge-muted transition",
        active ? "border-forge-amber/60 bg-[#24211b] text-forge-text" : "border-transparent hover:bg-[#181b1e]"
      ].join(" ")}
      onClick={onClick}
      aria-label={label}
      title={label}
    >
      {icon}
    </button>
  );
}

export function PanelTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2 border-b border-forge-line pb-2 text-sm font-semibold">
      {icon}
      <span>{title}</span>
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

export function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-forge-line bg-[#171716] p-2">
      <p className="text-forge-muted">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  );
}

export function EmptyPanel({ text }: { text: string }) {
  return <div className="rounded-md border border-dashed border-forge-line p-4 text-sm text-forge-muted">{text}</div>;
}
