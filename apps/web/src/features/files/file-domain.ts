import { api } from "../../lib/api";
import type { PlatformFile } from "../../types/api";

export type DuplicateFileDestination = "chat" | "library" | "chatgpt_import";

export type PendingDuplicateFile = {
  file: File;
  duplicate: PlatformFile;
  destination: DuplicateFileDestination;
  source: PlatformFile["source"];
};

export function platformFileLabel(platformFile: PlatformFile): string {
  return platformFile.filename || platformFile.original_filename || "arquivo";
}

export function fileContentUrl(fileId: string): string {
  return `${api.baseUrl}/api/files/${fileId}/content`;
}

export function isImagePlatformFile(platformFile: PlatformFile): boolean {
  if (platformFile.content_type?.startsWith("image/")) return true;
  return platformFileLabel(platformFile)
    .toLowerCase()
    .match(/\.(apng|avif|gif|jpe?g|png|svg|webp)$/)
    ? true
    : false;
}

export function metadataValue(metadata: Record<string, unknown>, key: string): string {
  const value = metadata[key];
  if (value === undefined || value === null) return "";
  return typeof value === "string" ? value : (JSON.stringify(value) ?? "");
}

export function isChatGPTInformationalFileName(fileName: string): boolean {
  const normalized = fileName.trim().toLowerCase();
  if (
    normalized === "conversations.json" ||
    normalized === "shared_conversations.json" ||
    normalized === "chat.html" ||
    normalized === "export_manifest.json" ||
    normalized === "user.json" ||
    normalized === "user_settings.json"
  ) {
    return true;
  }
  return /^conversations-\d+\.json$/i.test(normalized);
}
