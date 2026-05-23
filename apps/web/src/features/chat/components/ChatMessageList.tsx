import { ArrowUpRight, Flame, LoaderCircle } from "lucide-react";
import type { MutableRefObject } from "react";

import { MessageBubble, type ModelingPlanCardActions } from "../../../components/app-chat";
import { Mono } from "../../../components/ui/Mono";
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
  /** Resumo do rodapé do empty-state (dados reais). */
  sessionsCount: number;
  documentsCount: number;
  monthlySpendBrl: number | null;
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
  onQuickAction,
  sessionsCount,
  documentsCount,
  monthlySpendBrl
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
          <div className="mx-auto mt-10 flex w-full max-w-2xl flex-col items-center">
            <div className="mb-6 flex items-center gap-2.5">
              <span className="h-px w-8 bg-forge-line" />
              <Mono size={10} className="uppercase tracking-[0.2em] text-forge-faint">
                {new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })}
              </Mono>
              <span className="h-px w-8 bg-forge-line" />
            </div>
            <h1 className="text-center font-display text-4xl uppercase leading-none tracking-[0.005em] text-forge-text sm:text-5xl">
              Onde se descansa,
              <br />
              <span className="font-serif lowercase italic tracking-tight text-forge-amber">forja-se</span> a verdade.
            </h1>
            <p className="mt-4 max-w-md text-center text-sm leading-relaxed text-forge-muted">
              Escolha um ponto de partida ou escreva direto para a JUDITE.
            </p>
            <div className="mt-9 grid w-full gap-2.5 sm:grid-cols-2">
              {quickActions.map((action) => (
                <button
                  key={action}
                  className="flex items-center gap-3.5 rounded border border-forge-line-soft bg-forge-panel px-4 py-3.5 text-left transition hover:border-forge-amber/40"
                  onClick={() => onQuickAction(action)}
                >
                  <span
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] text-forge-amber"
                    style={{
                      background: "color-mix(in srgb, var(--ember) 10%, var(--bg-ink))",
                      border: "1px solid color-mix(in srgb, var(--ember) 20%, transparent)"
                    }}
                  >
                    <Flame size={16} />
                  </span>
                  <span className="min-w-0 flex-1 text-[13.5px] font-medium text-forge-text">{action}</span>
                  <ArrowUpRight size={14} className="shrink-0 text-forge-faint" />
                </button>
              ))}
            </div>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-x-3 gap-y-1.5">
              <Mono size={10} className="text-forge-faint">
                {sessionsCount} chats
              </Mono>
              {monthlySpendBrl != null && (
                <>
                  <span className="h-0.5 w-0.5 rounded-full bg-forge-faint" />
                  <Mono size={10} className="text-forge-faint">
                    R$ {monthlySpendBrl.toFixed(2).replace(".", ",")} gastos no mês
                  </Mono>
                </>
              )}
              <span className="h-0.5 w-0.5 rounded-full bg-forge-faint" />
              <Mono size={10} className="text-forge-faint">
                {documentsCount} documentos
              </Mono>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
