import { useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";

type ChatProjectScopeMode = "project_only" | "project_plus_global" | "global_only";

type ChatScopeSyncConfig = {
  activeSessionProjectId: string | null;
  chatProjectId: string | null;
  chatProjectScopeMode: ChatProjectScopeMode;
  setChatProjectId: Dispatch<SetStateAction<string | null>>;
  setChatProjectScopeMode: Dispatch<SetStateAction<ChatProjectScopeMode>>;
};

export function useChatScopeSync({
  activeSessionProjectId,
  chatProjectId,
  chatProjectScopeMode,
  setChatProjectId,
  setChatProjectScopeMode
}: ChatScopeSyncConfig): void {
  useEffect(() => {
    if (!activeSessionProjectId) {
      setChatProjectId(null);
      setChatProjectScopeMode("global_only");
      return;
    }
    setChatProjectId(activeSessionProjectId);
    setChatProjectScopeMode("project_only");
  }, [activeSessionProjectId, setChatProjectId, setChatProjectScopeMode]);

  useEffect(() => {
    if (!chatProjectId && chatProjectScopeMode !== "global_only") {
      setChatProjectScopeMode("global_only");
    }
  }, [chatProjectId, chatProjectScopeMode, setChatProjectScopeMode]);
}
