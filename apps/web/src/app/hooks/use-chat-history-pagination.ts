import { useEffect, useMemo, useRef, useState } from "react";
import type { MutableRefObject } from "react";

import type { ChatSession } from "../../types/api";

export function useChatHistoryPagination(
  sortedSessions: ChatSession[],
  activeSessionId: string | null,
  batchSize: number
): {
  historyLoadMoreRef: MutableRefObject<HTMLDivElement | null>;
  historyVisibleCount: number;
  visibleHistorySessions: ChatSession[];
} {
  const historyLoadMoreRef = useRef<HTMLDivElement | null>(null);
  const [historyRequestedCount, setHistoryRequestedCount] = useState(batchSize);
  const activeSessionIndex = useMemo(
    () => (activeSessionId ? sortedSessions.findIndex((session) => session.id === activeSessionId) : -1),
    [activeSessionId, sortedSessions]
  );
  const historyVisibleCount = useMemo(() => {
    const minimumForActiveSession = activeSessionIndex >= 0 ? activeSessionIndex + batchSize : batchSize;
    return Math.min(sortedSessions.length, Math.max(batchSize, historyRequestedCount, minimumForActiveSession));
  }, [activeSessionIndex, batchSize, historyRequestedCount, sortedSessions.length]);

  const visibleHistorySessions = useMemo(
    () => sortedSessions.slice(0, historyVisibleCount),
    [historyVisibleCount, sortedSessions]
  );

  useEffect(() => {
    const sentinel = historyLoadMoreRef.current;
    if (!sentinel || historyVisibleCount >= sortedSessions.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        setHistoryRequestedCount((current) => current + batchSize);
      },
      { root: null, rootMargin: "180px" }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [batchSize, historyVisibleCount, sortedSessions.length]);

  return { historyLoadMoreRef, historyVisibleCount, visibleHistorySessions };
}
