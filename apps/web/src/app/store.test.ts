import { beforeEach, describe, expect, it } from "vitest";

describe("useAppStore persistence", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it("migrates the removed modeling view to chat", async () => {
    localStorage.setItem(
      "truths-forge-ui-state-v1",
      JSON.stringify({
        state: {
          activeView: "modeling",
          activePanel: "config",
          activeSessionId: "chat_123"
        },
        version: 0
      })
    );

    const { useAppStore } = await import("./store");

    expect(useAppStore.getState().activeView).toBe("chat");
    expect(useAppStore.getState().activePanel).toBe("config");
    expect(useAppStore.getState().activeSessionId).toBe("chat_123");
  });

  it("strips stale modeling fields from persisted state", async () => {
    localStorage.setItem(
      "truths-forge-ui-state-v1",
      JSON.stringify({
        state: {
          activeView: "chat",
          activePanel: "contexto",
          modeling3dEnabled: true,
          modeling3dMode: "safe_auto",
          modeling3dSoftware: "blender"
        },
        version: 0
      })
    );

    const { useAppStore } = await import("./store");

    const state = useAppStore.getState();
    expect(state.activeView).toBe("chat");
    expect(state).not.toHaveProperty("modeling3dEnabled");
    expect(state).not.toHaveProperty("modeling3dMode");
    expect(state).not.toHaveProperty("modeling3dSoftware");
  });
});
