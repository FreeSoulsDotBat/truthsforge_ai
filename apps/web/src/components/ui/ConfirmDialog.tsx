import { useCallback, useEffect, useId, useRef } from "react";

import { cn } from "../../lib/utils";
import { Button } from "./Button";

export type ConfirmDialogTone = "default" | "danger";

export interface ConfirmDialogProps {
  /** Controls visibility — when ``false`` the dialog returns ``null``. */
  open: boolean;
  title: string;
  description?: string;
  /** Custom message slot (overrides ``description`` when provided). */
  children?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: ConfirmDialogTone;
  /** Disables the confirm button (e.g. while the action is running). */
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Accessible confirm dialog.
 *
 * Implementation notes:
 * - ``role=alertdialog`` + ``aria-modal=true`` + labelled by the title element.
 * - Initial focus moves to the confirm button so keyboard users land on the
 *   primary action immediately.
 * - ``ESC`` cancels; ``ENTER`` confirms when the focused element is not a
 *   secondary button (the focus trap keeps Tab cycling inside the dialog).
 * - The backdrop click also cancels. The body underneath gets the
 *   ``overflow-hidden`` class while the dialog is open so background scroll
 *   does not leak.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  children,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  tone = "default",
  busy = false,
  onConfirm,
  onCancel
}: ConfirmDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const confirmButtonRef = useRef<HTMLButtonElement | null>(null);
  const cancelButtonRef = useRef<HTMLButtonElement | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  // Trap focus inside the dialog while it is open and restore on close.
  useEffect(() => {
    if (!open) return undefined;
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    confirmButtonRef.current?.focus();
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
        onCancel();
        return;
      }
      if (event.key === "Tab") {
        // Two-element cycle between confirm and cancel buttons.
        const focusables = [confirmButtonRef.current, cancelButtonRef.current].filter(
          (node): node is HTMLButtonElement => !!node
        );
        if (focusables.length < 2) return;
        const active = document.activeElement as HTMLElement | null;
        const currentIndex = active ? focusables.indexOf(active as HTMLButtonElement) : -1;
        event.preventDefault();
        const nextIndex = event.shiftKey
          ? currentIndex <= 0
            ? focusables.length - 1
            : currentIndex - 1
          : (currentIndex + 1) % focusables.length;
        focusables[nextIndex]?.focus();
      }
    },
    [onCancel]
  );

  if (!open) {
    return null;
  }

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={description || children ? descriptionId : undefined}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onCancel();
        }
      }}
      onKeyDown={handleKeyDown}
    >
      <div
        className={cn(
          "w-full max-w-md rounded-md border bg-[#141615] p-5 shadow-xl",
          tone === "danger" ? "border-forge-red/60" : "border-forge-line"
        )}
      >
        <h2 id={titleId} className="text-base font-semibold text-forge-text">
          {title}
        </h2>
        {(description || children) && (
          <div id={descriptionId} className="mt-2 text-sm leading-6 text-forge-muted">
            {children ?? description}
          </div>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <Button ref={cancelButtonRef} type="button" disabled={busy} onClick={onCancel} className="h-9">
            {cancelLabel}
          </Button>
          <Button
            ref={confirmButtonRef}
            type="button"
            disabled={busy}
            onClick={onConfirm}
            className={cn(
              "h-9",
              tone === "danger" ? "border-forge-red/70 bg-[#2a1718]" : "border-forge-amber/60 bg-[#24211b]"
            )}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
