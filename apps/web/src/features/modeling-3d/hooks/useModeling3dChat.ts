import { useCallback } from "react";

import { toModeling3DContext } from "../api";
import { useModeling3DStore } from "../store";
import type { ChatModeling3DContext } from "../types";

export function useModeling3dChat() {
  const nextChatIs3D = useModeling3DStore((state) => state.nextChatIs3D);
  const software = useModeling3DStore((state) => state.software);
  const setNextChatIs3D = useModeling3DStore((state) => state.setNextChatIs3D);
  const setSoftware = useModeling3DStore((state) => state.setSoftware);
  const resetForNewChat = useModeling3DStore((state) => state.resetForNewChat);

  const chatContext = useCallback(
    (): ChatModeling3DContext => toModeling3DContext(nextChatIs3D, software) as ChatModeling3DContext,
    [nextChatIs3D, software]
  );

  return {
    nextChatIs3D,
    software,
    setNextChatIs3D,
    setSoftware,
    resetForNewChat,
    chatContext
  };
}
