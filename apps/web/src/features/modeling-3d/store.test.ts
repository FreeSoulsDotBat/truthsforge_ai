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
    // RF-001: a preferência de software NÃO é transiente — vale para os
    // próximos chats 3D (antes era zerada para "auto" a cada novo chat).
    expect(useModeling3DStore.getState().software).toBe("blender");

    useModeling3DStore.getState().setSoftware("auto");
    expect(useModeling3DStore.getState().software).toBe("auto");
  });

  it("persiste a preferência de software em localStorage", () => {
    useModeling3DStore.getState().setSoftware("fusion");
    expect(window.localStorage.getItem("tf.modeling3d.software")).toBe("fusion");
    useModeling3DStore.getState().setSoftware("auto");
  });
});
