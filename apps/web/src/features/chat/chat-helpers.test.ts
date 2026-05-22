import { describe, expect, it } from "vitest";

import {
  createDefaultKnowledgeBaseDraft,
  findMentionMatch,
  mergeUniqueMessages,
  normalizeMentionPart,
  sessionHasEmptyDraft
} from "./chat-helpers";

describe("chat-helpers (extracted from App.tsx)", () => {
  it("normalizeMentionPart trims and replaces spaces", () => {
    expect(normalizeMentionPart("  minha pasta  ")).toBe("minha_pasta");
  });

  it("findMentionMatch detects a trailing @mention", () => {
    const match = findMentionMatch("oi @Proj", 8);
    expect(match).toEqual({ start: 3, end: 8, query: "proj" });
  });

  it("findMentionMatch returns null when there is no mention", () => {
    expect(findMentionMatch("sem mencao", 10)).toBeNull();
  });

  it("mergeUniqueMessages dedupes by id, keeping order", () => {
    const older = [{ id: "a" }, { id: "b" }] as never[];
    const newer = [{ id: "b" }, { id: "c" }] as never[];
    expect(mergeUniqueMessages(older, newer).map((m) => (m as { id: string }).id)).toEqual(["a", "b", "c"]);
  });

  it("sessionHasEmptyDraft is true for a blank default chat", () => {
    const session = { title: "Novo chat", messages: [], metadata: {} } as never;
    expect(sessionHasEmptyDraft(session)).toBe(true);
  });

  it("createDefaultKnowledgeBaseDraft returns sane defaults", () => {
    const draft = createDefaultKnowledgeBaseDraft();
    expect(draft.enabled).toBe(true);
    expect(draft.max_documents_per_query).toBe(8);
  });
});
