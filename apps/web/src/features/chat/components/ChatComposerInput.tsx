import { ArrowUp, LoaderCircle } from "lucide-react";
import type { MutableRefObject } from "react";

import { KBD } from "../../../components/ui/KBD";
import { Mono } from "../../../components/ui/Mono";
import type { MentionOption } from "../chat-helpers";

export interface ChatComposerInputProps {
  showMentions: boolean;
  mentionSuggestions: MentionOption[];
  onInsertMention: (option: MentionOption) => void;
  draftInputRef: MutableRefObject<HTMLTextAreaElement | null>;
  draft: string;
  onChangeDraft: (value: string, cursor: number) => void;
  onMoveCursor: (cursor: number) => void;
  offline: boolean;
  modeling3dEnabled: boolean;
  sendButtonTitle: string;
  sendDisabled: boolean;
  isStreaming: boolean;
}

/**
 * Chat input row: the @-mention suggestions dropdown, the autosizing textarea
 * and the send button. Re-skin v4 "Hearth": botão de envio circular ember
 * (seta para cima) + dica de atalho ⌘↵. Extraído do App.tsx; apresentacional.
 */
export function ChatComposerInput({
  showMentions,
  mentionSuggestions,
  onInsertMention,
  draftInputRef,
  draft,
  onChangeDraft,
  onMoveCursor,
  offline,
  modeling3dEnabled,
  sendButtonTitle,
  sendDisabled,
  isStreaming
}: ChatComposerInputProps) {
  return (
    <>
      {showMentions && mentionSuggestions.length > 0 && (
        <div className="mb-2 rounded-md border border-forge-line-soft bg-forge-ink-deep p-1">
          <div className="px-2 pb-1 pt-0.5 text-[11px] text-forge-muted">Pastas de contexto</div>
          <div className="max-h-36 space-y-1 overflow-y-auto pr-1">
            {mentionSuggestions.map((option) => (
              <button
                key={option.key}
                type="button"
                className="flex w-full items-center justify-between rounded-sm px-2 py-1 text-left text-xs text-forge-muted transition hover:bg-forge-hover hover:text-forge-text"
                onClick={() => onInsertMention(option)}
              >
                <span className="truncate">{option.label}</span>
                <span className="ml-2 shrink-0 text-[10px] text-forge-amber">@</span>
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="flex items-end gap-2">
        <textarea
          ref={draftInputRef}
          value={draft}
          onChange={(event) =>
            onChangeDraft(event.target.value, event.target.selectionStart ?? event.target.value.length)
          }
          onClick={(event) => onMoveCursor((event.target as HTMLTextAreaElement).selectionStart ?? 0)}
          onKeyUp={(event) => onMoveCursor((event.target as HTMLTextAreaElement).selectionStart ?? 0)}
          rows={1}
          placeholder={
            offline
              ? "Servidor indisponível"
              : modeling3dEnabled
                ? "Descreva o modelo 3D para Blender/Fusion via MCP"
                : "Mensagem para JUDITE..."
          }
          disabled={offline}
          className="max-h-32 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-[14px] leading-relaxed text-forge-text placeholder:text-forge-muted focus:outline-none"
        />
        <div className="flex items-center gap-2 pb-0.5">
          <Mono size={10} className="hidden items-center gap-1 text-forge-faint sm:flex">
            <KBD>⌘</KBD>
            <KBD>↵</KBD>
            enviar
          </Mono>
          <button
            type="submit"
            disabled={sendDisabled}
            aria-label="Enviar"
            title={sendButtonTitle}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition disabled:cursor-not-allowed"
            style={{
              background: sendDisabled ? "var(--bg-chip)" : "var(--ember)",
              color: sendDisabled ? "var(--faint)" : "var(--ember-ink)",
              boxShadow: sendDisabled ? undefined : "0 8px 24px -10px var(--ember-glow)"
            }}
          >
            {isStreaming ? <LoaderCircle size={16} className="animate-spin" /> : <ArrowUp size={16} strokeWidth={2} />}
          </button>
        </div>
      </div>
    </>
  );
}
