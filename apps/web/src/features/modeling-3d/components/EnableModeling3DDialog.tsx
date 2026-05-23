import { useCallback, useEffect, useId, useRef } from "react";

import type { ModelingSoftware } from "../types";

type EnableModeling3DDialogProps = {
  open: boolean;
  software: ModelingSoftware;
  onClose: () => void;
  onConfirm: () => void;
  onSoftwareChange: (value: ModelingSoftware) => void;
};

export function EnableModeling3DDialog({
  open,
  software,
  onClose,
  onConfirm,
  onSoftwareChange
}: EnableModeling3DDialogProps) {
  const titleId = useId();
  const confirmRef = useRef<HTMLButtonElement | null>(null);
  const cancelRef = useRef<HTMLButtonElement | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return undefined;
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    confirmRef.current?.focus();
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
        return;
      }
      if (event.key === "Tab") {
        const focusables = [confirmRef.current, cancelRef.current].filter((node): node is HTMLButtonElement => !!node);
        if (focusables.length < 2) return;
        const currentIndex = focusables.indexOf(document.activeElement as HTMLButtonElement);
        event.preventDefault();
        const nextIndex = event.shiftKey
          ? currentIndex <= 0
            ? focusables.length - 1
            : currentIndex - 1
          : (currentIndex + 1) % focusables.length;
        focusables[nextIndex]?.focus();
      }
    },
    [onClose]
  );

  if (!open) return null;

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      onKeyDown={handleKeyDown}
    >
      <div className="w-full max-w-md rounded-lg border border-forge-line bg-forge-panel p-4 shadow-[0_16px_36px_-20px_var(--amethyst-glow)]">
        <div className="space-y-1">
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-forge-amethyst">MCP 3D</p>
          <h3 id={titleId} className="font-display text-lg uppercase tracking-[0.015em] text-forge-text">
            Ativar modelagem 3D no chat
          </h3>
          <p className="text-sm text-forge-muted">
            O próximo chat será marcado como 3D e JUDITE executará adições e alterações normais via MCP fluido. Deleções
            e ações destrutivas continuam abrindo aprovação humana.
          </p>
        </div>
        <div className="mt-4 grid gap-3">
          <label className="grid gap-1 text-xs text-forge-muted">
            Software
            <select
              value={software}
              onChange={(event) => onSoftwareChange(event.target.value as ModelingSoftware)}
              className="h-9 rounded-md border border-forge-line bg-forge-ink-deep px-3 text-sm text-forge-text"
            >
              <option value="auto">Auto</option>
              <option value="blender">Blender</option>
              <option value="fusion">Fusion 360</option>
            </select>
          </label>
          <p className="rounded-md border border-forge-line bg-forge-ink-deep px-3 py-2 text-xs text-forge-muted">
            Modo: fluido allowlistado. O plano estruturado fica auditável no chat, sem etapa separada de aprovação para
            operações seguras.
          </p>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button
            ref={cancelRef}
            type="button"
            className="rounded-md border border-forge-line px-3 py-2 text-sm text-forge-muted hover:text-forge-text"
            onClick={onClose}
          >
            Cancelar
          </button>
          <button
            ref={confirmRef}
            type="button"
            className="rounded-md border border-[color-mix(in_srgb,var(--amethyst)_50%,transparent)] bg-[color-mix(in_srgb,var(--amethyst)_16%,transparent)] px-3 py-2 text-sm font-medium text-forge-amethyst transition hover:bg-[color-mix(in_srgb,var(--amethyst)_24%,transparent)]"
            onClick={onConfirm}
          >
            Ativar no próximo chat
          </button>
        </div>
      </div>
    </div>
  );
}
