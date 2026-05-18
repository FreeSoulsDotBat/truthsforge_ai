import { describe, expect, it } from "vitest";

import { useModeling3DStore } from "./store";

describe("useModeling3DStore", () => {
  it("keeps nextChatIs3D as transient feature state", () => {
    useModeling3DStore.getState().resetForNewChat();
    useModeling3DStore.getState().enableNextChat();
    useModeling3DStore.getState().setSoftware("blender");

    expect(useModeling3DStore.getState().nextChatIs3D).toBe(true);
    expect(useModeling3DStore.getState().software).toBe("blender");

    useModeling3DStore.getState().resetForNewChat();

    expect(useModeling3DStore.getState().nextChatIs3D).toBe(false);
    expect(useModeling3DStore.getState().software).toBe("auto");
  });
});
