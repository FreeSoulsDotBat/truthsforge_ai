import type { ChatSession } from "./types";

export function isModeling3DChat(session: Pick<ChatSession, "is_modeling_3d" | "metadata"> | null | undefined) {
  if (!session) return false;
  const metadata = session.metadata as Record<string, unknown> | undefined;
  const modelingMetadata = metadata?.modeling_3d as Record<string, unknown> | undefined;
  return session.is_modeling_3d === true || modelingMetadata?.enabled === true;
}
