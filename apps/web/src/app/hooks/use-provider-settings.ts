import { useState } from "react";

import { api } from "../../lib/api";
import type { ProviderModel, ProviderName, ProviderSecretStatus } from "../../types/api";
import type { ProviderCatalogState } from "../ui-state";

type ProviderSettingsConfig = {
  /** Apply an updated secret status to the app's provider list. */
  onProviderStatus: (provider: ProviderName, status: ProviderSecretStatus) => void;
  /** Re-fetch the app-data snapshot after a secret changes. */
  refresh: () => void;
};

/**
 * Owns the provider-settings UI state (key drafts, edit mode, model catalogs)
 * and the save/clear/list-models actions. Extracted from App.tsx
 * (architecture-map "monólitos de borda") to shrink the component and let the
 * React Compiler analyse this slice independently. The server-owned provider
 * status list stays in App and is updated through `onProviderStatus`.
 */
export function useProviderSettings({ onProviderStatus, refresh }: ProviderSettingsConfig) {
  const [providerDrafts, setProviderDrafts] = useState<Record<string, string>>({});
  const [providerEditMode, setProviderEditMode] = useState<Record<string, boolean>>({});
  const [providerCatalogs, setProviderCatalogs] = useState<Partial<Record<ProviderName, ProviderModel[]>>>({});
  const [providerCatalogState, setProviderCatalogState] = useState<Partial<Record<ProviderName, ProviderCatalogState>>>(
    {}
  );
  const [providerCatalogErrors, setProviderCatalogErrors] = useState<Partial<Record<ProviderName, string>>>({});

  async function saveProviderKey(provider: ProviderName) {
    const apiKey = providerDrafts[provider]?.trim();
    if (!apiKey) return;
    const status = await api.saveProviderKey(provider, apiKey);
    onProviderStatus(provider, status);
    setProviderDrafts((current) => ({ ...current, [provider]: "" }));
    setProviderEditMode((current) => ({ ...current, [provider]: false }));
    refresh();
  }

  async function clearProviderKey(provider: ProviderName) {
    const status = await api.deleteProviderKey(provider);
    onProviderStatus(provider, status);
    setProviderDrafts((current) => ({ ...current, [provider]: "" }));
    setProviderEditMode((current) => ({ ...current, [provider]: false }));
    refresh();
  }

  async function loadProviderModels(provider: ProviderName) {
    setProviderCatalogState((current) => ({ ...current, [provider]: "loading" }));
    setProviderCatalogErrors((current) => ({ ...current, [provider]: "" }));
    try {
      const providerModels = await api.providerModels(provider);
      setProviderCatalogs((current) => ({ ...current, [provider]: providerModels }));
      setProviderCatalogState((current) => ({ ...current, [provider]: "ready" }));
    } catch (error) {
      setProviderCatalogState((current) => ({ ...current, [provider]: "error" }));
      setProviderCatalogErrors((current) => ({
        ...current,
        [provider]: error instanceof Error ? error.message : "Falha ao listar modelos"
      }));
    }
  }

  return {
    providerDrafts,
    setProviderDrafts,
    providerEditMode,
    setProviderEditMode,
    providerCatalogs,
    providerCatalogState,
    providerCatalogErrors,
    saveProviderKey,
    clearProviderKey,
    loadProviderModels
  };
}
