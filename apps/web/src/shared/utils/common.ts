import type { ChatSession } from "../../types/api";

export function optionalNumber(value: unknown): number | null {
  if (value === undefined || value === null || value === "") return null;
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
}

export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

export function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = value / 1024;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 ? 1 : 2)} ${units[unitIndex]}`;
}

export function timestampMillis(value?: string | null): number {
  if (!value) return 0;
  const normalized = value.trim();
  if (!normalized) return 0;
  const numeric = Number(normalized);
  if (Number.isFinite(numeric) && numeric > 0) {
    return numeric > 10_000_000_000 ? numeric : numeric * 1000;
  }
  const parsed = Date.parse(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function sortSessionsByNewest(list: ChatSession[]): ChatSession[] {
  return [...list].sort((left, right) => {
    const leftTime = timestampMillis(left.updated_at || left.created_at);
    const rightTime = timestampMillis(right.updated_at || right.created_at);
    if (rightTime !== leftTime) return rightTime - leftTime;
    const leftCreated = timestampMillis(left.created_at);
    const rightCreated = timestampMillis(right.created_at);
    if (rightCreated !== leftCreated) return rightCreated - leftCreated;
    return right.id.localeCompare(left.id);
  });
}

export function csvToList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export const numericDraftPattern = /^-?\d*(?:[.,]\d*)?$/;
export const incompleteNumericDrafts = new Set(["-", ".", ",", "-.", "-,"]);

export function numberInputDraft(value: number | string | null | undefined): string {
  if (value === undefined || value === null || value === "") return "";
  if (typeof value === "number" && Number.isNaN(value)) return "";
  return String(value);
}

export function normalizeNumberDraft(value: string): string {
  return value.trim().replace(",", ".");
}
