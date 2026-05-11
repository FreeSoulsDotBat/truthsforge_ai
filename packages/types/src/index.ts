export type ProviderName = "openai" | "anthropic" | "google";

export interface ApiEnvelope<T> {
  data: T;
  requestId?: string;
}
