import { useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";

type ChatScopeSyncConfig = {
  activeSessionProjectId: string | null;
  setChatProjectId: Dispatch<SetStateAction<string | null>>;
};

// Nota 2026-06: `chatProjectScopeMode` foi removido do store (estado morto —
// nenhum payload do front enviava `project_scope_mode`; a única emissão vivia
// no stream de chat e já tinha sido retirada). Este hook agora só mantém o
// `chatProjectId` espelhando o projeto da sessão ativa.
export function useChatScopeSync({ activeSessionProjectId, setChatProjectId }: ChatScopeSyncConfig): void {
  useEffect(() => {
    setChatProjectId(activeSessionProjectId ?? null);
  }, [activeSessionProjectId, setChatProjectId]);
}
