import type { SetStateAction } from "react";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { DashboardView, Panel } from "./ui-state";

type ReasoningOverride = "default" | "long";
type ResponseMode = "text" | "image";
type ShortcutSubmenu = "agent" | "scope" | null;

type Updater<T> = SetStateAction<T>;
const dashboardViews: DashboardView[] = ["chat", "agents", "projects", "knowledge", "files"];

function applyUpdater<T>(current: T, next: Updater<T>): T {
  return typeof next === "function" ? (next as (value: T) => T)(current) : next;
}

function isDashboardView(value: unknown): value is DashboardView {
  return typeof value === "string" && dashboardViews.includes(value as DashboardView);
}

// `chatProjectScopeMode` virou estado morto quando o payload do stream parou
// de enviar `project_scope_mode`; removido do store em 2026-06 (nenhum payload
// do front lia o valor — só set/sync/persist).
const staleKeys = ["modeling3dEnabled", "modeling3dMode", "modeling3dSoftware", "chatProjectScopeMode"] as const;

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function migratePersistedState(persistedState: unknown, version: number): unknown {
  if (!persistedState || typeof persistedState !== "object") {
    return persistedState;
  }

  const state = { ...(persistedState as Record<string, unknown>) };

  for (const key of staleKeys) {
    delete state[key];
  }

  if (!isDashboardView(state.activeView)) {
    state.activeView = initialState.activeView;
  }

  return state;
}

export type AppStoreState = {
  activeView: DashboardView;
  activePanel: Panel;
  activeSessionId: string | null;
  activeAgentId: string | null;
  supportAgentIds: string[];
  selectedKnowledgeProjectId: string | null;
  selectedKnowledgeFolderId: string | null;
  chatProjectId: string | null;
  reasoningOverride: ReasoningOverride;
  deepResearch: boolean;
  deepResearchMaxToolCalls: number;
  responseMode: ResponseMode;
  imageModelId: string | null;
  reasoningSummary: boolean;
  multiAgentMode: boolean;
  shortcutMenuOpen: boolean;
  shortcutSubmenu: ShortcutSubmenu;
  executionMenuOpen: boolean;
  mobileMenuOpen: boolean;
};

type AppStoreActions = {
  setActiveView: (next: Updater<DashboardView>) => void;
  setActivePanel: (next: Updater<Panel>) => void;
  setActiveSessionId: (next: Updater<string | null>) => void;
  setActiveAgentId: (next: Updater<string | null>) => void;
  setSupportAgentIds: (next: Updater<string[]>) => void;
  setSelectedKnowledgeProjectId: (next: Updater<string | null>) => void;
  setSelectedKnowledgeFolderId: (next: Updater<string | null>) => void;
  setChatProjectId: (next: Updater<string | null>) => void;
  setReasoningOverride: (next: Updater<ReasoningOverride>) => void;
  setDeepResearch: (next: Updater<boolean>) => void;
  setDeepResearchMaxToolCalls: (next: Updater<number>) => void;
  setResponseMode: (next: Updater<ResponseMode>) => void;
  setImageModelId: (next: Updater<string | null>) => void;
  setReasoningSummary: (next: Updater<boolean>) => void;
  setMultiAgentMode: (next: Updater<boolean>) => void;
  setShortcutMenuOpen: (next: Updater<boolean>) => void;
  setShortcutSubmenu: (next: Updater<ShortcutSubmenu>) => void;
  setExecutionMenuOpen: (next: Updater<boolean>) => void;
  setMobileMenuOpen: (next: Updater<boolean>) => void;
};

type AppStore = AppStoreState & AppStoreActions;

const initialState: AppStoreState = {
  activeView: "chat",
  activePanel: "contexto",
  activeSessionId: null,
  activeAgentId: null,
  supportAgentIds: [],
  selectedKnowledgeProjectId: null,
  selectedKnowledgeFolderId: null,
  chatProjectId: null,
  reasoningOverride: "default",
  deepResearch: false,
  deepResearchMaxToolCalls: 12,
  responseMode: "text",
  imageModelId: null,
  reasoningSummary: false,
  multiAgentMode: false,
  shortcutMenuOpen: false,
  shortcutSubmenu: null,
  executionMenuOpen: false,
  mobileMenuOpen: false
};

export const useAppStore = create<AppStore>()(
  persist(
    (set) => ({
      ...initialState,
      setActiveView: (next) => set((state) => ({ activeView: applyUpdater(state.activeView, next) })),
      setActivePanel: (next) => set((state) => ({ activePanel: applyUpdater(state.activePanel, next) })),
      setActiveSessionId: (next) => set((state) => ({ activeSessionId: applyUpdater(state.activeSessionId, next) })),
      setActiveAgentId: (next) => set((state) => ({ activeAgentId: applyUpdater(state.activeAgentId, next) })),
      setSupportAgentIds: (next) => set((state) => ({ supportAgentIds: applyUpdater(state.supportAgentIds, next) })),
      setSelectedKnowledgeProjectId: (next) =>
        set((state) => ({ selectedKnowledgeProjectId: applyUpdater(state.selectedKnowledgeProjectId, next) })),
      setSelectedKnowledgeFolderId: (next) =>
        set((state) => ({ selectedKnowledgeFolderId: applyUpdater(state.selectedKnowledgeFolderId, next) })),
      setChatProjectId: (next) => set((state) => ({ chatProjectId: applyUpdater(state.chatProjectId, next) })),
      setReasoningOverride: (next) =>
        set((state) => ({ reasoningOverride: applyUpdater(state.reasoningOverride, next) })),
      setDeepResearch: (next) => set((state) => ({ deepResearch: applyUpdater(state.deepResearch, next) })),
      setDeepResearchMaxToolCalls: (next) =>
        set((state) => ({ deepResearchMaxToolCalls: applyUpdater(state.deepResearchMaxToolCalls, next) })),
      setResponseMode: (next) => set((state) => ({ responseMode: applyUpdater(state.responseMode, next) })),
      setImageModelId: (next) => set((state) => ({ imageModelId: applyUpdater(state.imageModelId, next) })),
      setReasoningSummary: (next) => set((state) => ({ reasoningSummary: applyUpdater(state.reasoningSummary, next) })),
      setMultiAgentMode: (next) => set((state) => ({ multiAgentMode: applyUpdater(state.multiAgentMode, next) })),
      setShortcutMenuOpen: (next) => set((state) => ({ shortcutMenuOpen: applyUpdater(state.shortcutMenuOpen, next) })),
      setShortcutSubmenu: (next) => set((state) => ({ shortcutSubmenu: applyUpdater(state.shortcutSubmenu, next) })),
      setExecutionMenuOpen: (next) =>
        set((state) => ({ executionMenuOpen: applyUpdater(state.executionMenuOpen, next) })),
      setMobileMenuOpen: (next) => set((state) => ({ mobileMenuOpen: applyUpdater(state.mobileMenuOpen, next) }))
    }),
    {
      name: "truths-forge-ui-state-v1",
      // v2 (2026-06): remove `chatProjectScopeMode` do localStorage — sem o
      // bump o `migrate` não roda (só dispara em mismatch de versão) e o merge
      // raso da rehidratação reinjetaria a chave morta no store.
      version: 2,
      storage: createJSONStorage(() => localStorage),
      migrate: migratePersistedState,
      partialize: (state) => ({
        activeView: state.activeView,
        activePanel: state.activePanel,
        activeSessionId: state.activeSessionId,
        activeAgentId: state.activeAgentId,
        supportAgentIds: state.supportAgentIds,
        selectedKnowledgeProjectId: state.selectedKnowledgeProjectId,
        selectedKnowledgeFolderId: state.selectedKnowledgeFolderId,
        chatProjectId: state.chatProjectId,
        reasoningOverride: state.reasoningOverride,
        deepResearch: state.deepResearch,
        deepResearchMaxToolCalls: state.deepResearchMaxToolCalls,
        responseMode: state.responseMode,
        imageModelId: state.imageModelId,
        reasoningSummary: state.reasoningSummary,
        multiAgentMode: state.multiAgentMode
      })
    }
  )
);
