/**
 * Pure, module-level chat helpers extracted from `App.tsx`
 * (architecture-map finding "monólitos de borda"). Keeping them here trims the
 * App component and makes the helpers independently unit-testable.
 */
import type { ChatMessageAttachment } from "./chat-domain";
import { fileContentUrl } from "../files/file-domain";
import type {
  ChatMessage,
  ChatSession,
  KnowledgeBaseUpsert,
  PlatformFile
} from "../../types/api";

export type SessionLazyMeta = {
  hasMore: boolean;
  loadingOlder: boolean;
};

export type MentionMatch = {
  start: number;
  end: number;
  query: string;
};

export type MentionOption = {
  key: string;
  label: string;
  token: string;
};

export const CONTEXT_MODAL_SEEN_PROJECTS_STORAGE_KEY = "truths_forge.context_modal_seen_projects.v1";
export const FRONTEND_DUPLICATE_HASH_LIMIT_BYTES = 100 * 1024 * 1024;
export const DOCUMENT_SNAPSHOT_PAGE_SIZE = 80;

export function normalizeMentionPart(value: string): string {
  return value.trim().replace(/ /g, "_");
}

export function loadSeenContextModalProjectIds(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(CONTEXT_MODAL_SEEN_PROJECTS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((value): value is string => typeof value === "string" && value.trim().length > 0);
  } catch {
    return [];
  }
}

export function findMentionMatch(input: string, cursor: number): MentionMatch | null {
  const boundedCursor = Math.max(0, Math.min(cursor, input.length));
  const beforeCursor = input.slice(0, boundedCursor);
  const atIndex = beforeCursor.lastIndexOf("@");
  if (atIndex < 0) return null;
  if (atIndex > 0 && /[\w./-]/.test(beforeCursor[atIndex - 1] ?? "")) {
    return null;
  }
  const mentionRaw = beforeCursor.slice(atIndex + 1);
  if (/[^A-Za-z0-9_./-]/.test(mentionRaw)) return null;
  return {
    start: atIndex,
    end: boundedCursor,
    query: mentionRaw.toLowerCase()
  };
}

export function mergeUniqueMessages(older: ChatMessage[], newer: ChatMessage[]): ChatMessage[] {
  const seen = new Set<string>();
  const merged: ChatMessage[] = [];
  for (const message of [...older, ...newer]) {
    if (seen.has(message.id)) continue;
    seen.add(message.id);
    merged.push(message);
  }
  return merged;
}

export function sessionHasEmptyDraft(session: ChatSession): boolean {
  const metadata = session.metadata as Record<string, unknown> | undefined;
  if (metadata?.is_empty_draft === true) return true;
  if ((session.messages?.length ?? 0) > 0) return false;
  const normalizedTitle = session.title.trim().toLowerCase();
  return normalizedTitle === "novo chat" || normalizedTitle === "new chat";
}

export function createChatAttachmentPreview(platformFile: PlatformFile): ChatMessageAttachment {
  return {
    id: platformFile.id,
    file_id: platformFile.id,
    filename: platformFile.filename,
    original_filename: platformFile.original_filename,
    content_type: platformFile.content_type,
    size_bytes: platformFile.size_bytes,
    url: fileContentUrl(platformFile.id)
  };
}

export async function sha256BrowserFile(file: File): Promise<string | null> {
  if (!globalThis.crypto?.subtle || file.size > FRONTEND_DUPLICATE_HASH_LIMIT_BYTES) {
    return null;
  }
  const digest = await globalThis.crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export function createDefaultKnowledgeBaseDraft(): KnowledgeBaseUpsert {
  return {
    name: "",
    description: "",
    scope: "",
    color: "#f0b84d",
    tags: [],
    max_documents_per_query: 8,
    max_chunks_per_document: 3,
    enabled: true,
    metadata: {}
  };
}
