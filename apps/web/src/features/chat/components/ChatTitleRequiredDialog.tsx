import { Check, X } from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";

import { Button } from "../../../components/ui/Button";
import { isDefaultChatTitle, normalizeRequiredChatTitle } from "../chat-domain";

type ChatTitleRequiredDialogProps = {
  open: boolean;
  initialTitle?: string;
  onConfirm: (title: string) => Promise<void> | void;
  onCancel?: () => void;
  busy?: boolean;
};

export function ChatTitleRequiredDialog({
  open,
  initialTitle = "",
  onConfirm,
  onCancel,
  busy = false
}: ChatTitleRequiredDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const inputId = useId();
  const [titleDraft, setTitleDraft] = useState(initialTitle);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const cancelRef = useRef<HTMLButtonElement | null>(null);
  const confirmRef = useRef<HTMLButtonElement | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return undefined;
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    document.body.classList.add("overflow-hidden");
    requestAnimationFrame(() => inputRef.current?.focus());
    return () => {
      document.body.classList.remove("overflow-hidden");
      previouslyFocusedRef.current?.focus?.();
    };
  }, [open]);

  const normalizedTitle = normalizeRequiredChatTitle(titleDraft);
  const confirmDisabled = busy || isDefaultChatTitle(normalizedTitle);
  const validationMessage = useMemo(() => {
    if (!titleDraft.trim()) return "Digite um título para continuar.";
    if (isDefaultChatTitle(titleDraft)) return "Escolha um título diferente de Novo chat.";
    return null;
  }, [titleDraft]);

  const handleCancel = useCallback(() => {
    if (busy) return;
    onCancel?.();
  }, [busy, onCancel]);

  const handleConfirm = useCallback(() => {
    if (confirmDisabled) return;
    void onConfirm(normalizedTitle);
  }, [confirmDisabled, normalizedTitle, onConfirm]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        handleCancel();
        return;
      }
      if (event.key === "Tab") {
        const focusables = [inputRef.current, cancelRef.current, confirmRef.current].filter(
          (node): node is HTMLButtonElement | HTMLInputElement => !!node && !node.disabled
        );
        if (focusables.length < 2) return;
        const currentIndex = focusables.findIndex((node) => node === document.activeElement);
        event.preventDefault();
        const nextIndex = event.shiftKey
          ? currentIndex <= 0
            ? focusables.length - 1
            : currentIndex - 1
          : (currentIndex + 1) % focusables.length;
        focusables[nextIndex]?.focus();
      }
    },
    [handleCancel]
  );

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
      onClick={(event) => {
        if (event.target === event.currentTarget) handleCancel();
      }}
      onKeyDown={handleKeyDown}
    >
      <form
        className="w-full max-w-md rounded-md border border-forge-line bg-[#141615] p-5 shadow-xl"
        onSubmit={(event) => {
          event.preventDefault();
          handleConfirm();
        }}
      >
        <div className="space-y-2">
          <p className="text-xs uppercase text-forge-muted">Novo chat</p>
          <h2 id={titleId} className="text-base font-semibold text-forge-text">
            Dê um título antes de começar
          </h2>
          <p id={descriptionId} className="text-sm leading-6 text-forge-muted">
            Dê um título para esse chat antes de começar: isso ajuda você a encontrá-lo depois e economiza chamadas ao
            modelo.
          </p>
        </div>

        <label htmlFor={inputId} className="mt-5 grid gap-2 text-xs font-medium text-forge-muted">
          Título do chat
          <input
            ref={inputRef}
            id={inputId}
            value={titleDraft}
            minLength={1}
            autoFocus
            disabled={busy}
            onChange={(event) => setTitleDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== "Enter") return;
              event.preventDefault();
              handleConfirm();
            }}
            className="h-10 rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text outline-none transition placeholder:text-forge-muted focus:border-forge-amber/70"
            placeholder="Ex.: Suporte de mesa para headphone"
          />
        </label>
        {validationMessage && <p className="mt-2 text-xs text-forge-muted">{validationMessage}</p>}

        <div className="mt-5 flex justify-end gap-2">
          <Button ref={cancelRef} type="button" disabled={busy} onClick={handleCancel} className="h-9">
            <X size={15} />
            Cancelar
          </Button>
          <Button
            ref={confirmRef}
            type="submit"
            disabled={confirmDisabled}
            className="h-9 border-forge-amber/60 bg-[#24211b]"
          >
            <Check size={15} />
            Confirmar
          </Button>
        </div>
      </form>
    </div>
  );
}
