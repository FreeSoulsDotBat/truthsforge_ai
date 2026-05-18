import { useCallback, useMemo, useRef, useState } from "react";

import type { ChatSession } from "../../../types/api";
import { chatSessionNeedsTitle, isDefaultChatTitle, normalizeRequiredChatTitle } from "../chat-domain";

type TitleResolver = (title: string | null) => void;

export function useChatTitleGate(activeSession: ChatSession | null) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [initialTitle, setInitialTitle] = useState("");
  const [dialogRequestId, setDialogRequestId] = useState(0);
  const resolverRef = useRef<TitleResolver | null>(null);

  const needsTitle = useMemo(() => chatSessionNeedsTitle(activeSession), [activeSession]);

  const openTitleDialog = useCallback(
    (title?: string | null) =>
      new Promise<string | null>((resolve) => {
        resolverRef.current?.(null);
        resolverRef.current = resolve;
        const normalized = normalizeRequiredChatTitle(title ?? activeSession?.title);
        setInitialTitle(isDefaultChatTitle(normalized) ? "" : normalized);
        setDialogRequestId((current) => current + 1);
        setDialogOpen(true);
      }),
    [activeSession?.title]
  );

  const confirmTitle = useCallback((title: string) => {
    const normalized = normalizeRequiredChatTitle(title);
    if (isDefaultChatTitle(normalized)) return;
    setDialogOpen(false);
    resolverRef.current?.(normalized);
    resolverRef.current = null;
  }, []);

  const cancelTitleDialog = useCallback(() => {
    setDialogOpen(false);
    resolverRef.current?.(null);
    resolverRef.current = null;
  }, []);

  return {
    needsTitle,
    dialogOpen,
    dialogRequestId,
    initialTitle,
    openTitleDialog,
    confirmTitle,
    cancelTitleDialog
  };
}
