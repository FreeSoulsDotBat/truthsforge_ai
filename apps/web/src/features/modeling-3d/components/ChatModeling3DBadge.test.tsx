import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { isModeling3DChat } from "../chat-domain";
import type { ChatSession } from "../types";
import { ChatModeling3DBadge } from "./ChatModeling3DBadge";

const baseSession: Pick<ChatSession, "is_modeling_3d" | "metadata"> = {
  is_modeling_3d: false,
  metadata: {}
};

describe("ChatModeling3DBadge", () => {
  it("renders accessible 3D badge", () => {
    render(<ChatModeling3DBadge />);
    expect(screen.getByLabelText("Chat de modelagem 3D")).toBeTruthy();
    expect(screen.getByText("3D")).toBeTruthy();
  });

  it("detects persisted 3D chats by dedicated flag", () => {
    expect(isModeling3DChat({ ...baseSession, is_modeling_3d: true })).toBe(true);
  });

  it("falls back to legacy metadata when the flag is absent", () => {
    expect(isModeling3DChat({ metadata: { modeling_3d: { enabled: true } } })).toBe(true);
  });

  it("returns false for normal chats", () => {
    expect(isModeling3DChat(baseSession)).toBe(false);
    expect(isModeling3DChat(null)).toBe(false);
  });
});
