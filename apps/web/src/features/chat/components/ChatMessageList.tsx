import { Bot, LoaderCircle } from "lucide-react";
import type { MutableRefObject } from "react";

import { MessageBubble, type ModelingPlanCardActions } from "../../../components/app-chat";
import type { ChatMessage, ChatSession, PlatformFile } from "../../../types/api";
import type { SessionLazyMeta } from "../chat-helpers";

export interface ChatMessageListProps {
  activeSession: ChatSession | null;
  activeSessionLazy: SessionLazyMeta | undefined;
  platformFilesById: Record<string, PlatformFile>;
  isModeling3D: boolean;
  modelingPlanActions: ModelingPlanCardActions;
  scrollRef: MutableRefObject<HTMLDivElement | null>;
  loadOlderRef: MutableRefObject<HTMLDivElement | null>;
  onScroll: () => void;
  quickActions: readonly string[];
  onQuickAction: (action: string) => void;
}

/**
 * Chat message scroll area: lazy-load sentinel, the message list and the
 * empty-state quick actions. Extracted from App.tsx (architecture-map finding
 * "monólitos de borda"); purely presentational.
 */
export function ChatMessageList({
  activeSession,
  activeSessionLazy,
  platformFilesById,
  isModeling3D,
  modelingPlanActions,
  scrollRef,
  loadOlderRef,
  onScroll,
  quickActions,
  onQuickAction
}: ChatMessageListProps) {
  const messages: ChatMessage[] = activeSession?.messages.length ? activeSession.messages : [];
  return (
    <div ref={scrollRef} onScroll={onScroll} className="scrollbar-slim min-h-0 flex-1 overflow-y-auto px-4 py-5">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        {!!activeSession?.messages.length && activeSessionLazy?.hasMore && (
          <div ref={loadOlderRef} className="flex h-7 items-center justify-center text-xs text-forge-muted">
            {activeSessionLazy.loadingOlder ? (
              <span className="inline-flex items-center gap-2">
                <LoaderCircle size={14} className="animate-spin" />
                Carregando mensagens antigas...
              </span>
            ) : (
              "Role para cima para carregar mais"
            )}
          </div>
        )}
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            platformFilesById={platformFilesById}
            modelingPlanActions={isModeling3D ? modelingPlanActions : undefined}
          />
        ))}

        {!activeSession?.messages.length && (
          <div className="mx-auto mt-12 w-full max-w-2xl">
            <div className="mb-6 text-center">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-md border border-forge-line bg-[#171716]">
                <Bot size={28} className="text-forge-amber" />
              </div>
              <h3 className="text-xl font-semibold">Como posso ajudar agora?</h3>
              <p className="mt-2 text-sm leading-6 text-forge-muted">
                Escolha um ponto de partida ou escreva direto para a JUDITE.
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {quickActions.map((action) => (
                <button
                  key={action}
                  className="min-h-12 rounded-md border border-forge-line bg-[#141615] px-3 py-2 text-left text-sm text-forge-text transition hover:border-forge-amber/60 hover:bg-[#1b1d1b]"
                  onClick={() => onQuickAction(action)}
                >
                  {action}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
