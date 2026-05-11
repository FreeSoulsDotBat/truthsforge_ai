import type { SetStateAction } from "react";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { DashboardView, Panel } from "./ui-state";

type ChatProjectScopeMode = "project_only" | "project_plus_global" | "global_only";
type ReasoningOverride = "default" | "long";
type ResponseMode = "text" | "image";
type ShortcutSubmenu = "agent" | "scope" | null;

type Updater<T> = SetStateAction<T>;

function applyUpdater<T>(current: T, next: Updater<T>): T {
  return typeof next === "function" ? (next as (value: T) => T)(current) : next;
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
  chatProjectScopeMode: ChatProjectScopeMode;
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
  setChatProjectScopeMode: (next: Updater<ChatProjectScopeMode>) => void;
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
  chatProjectScopeMode: "global_only",
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
      setChatProjectScopeMode: (next) =>
        set((state) => ({ chatProjectScopeMode: applyUpdater(state.chatProjectScopeMode, next) })),
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
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        activeView: state.activeView,
        activePanel: state.activePanel,
        activeSessionId: state.activeSessionId,
        activeAgentId: state.activeAgentId,
        supportAgentIds: state.supportAgentIds,
        selectedKnowledgeProjectId: state.selectedKnowledgeProjectId,
        selectedKnowledgeFolderId: state.selectedKnowledgeFolderId,
        chatProjectId: state.chatProjectId,
        chatProjectScopeMode: state.chatProjectScopeMode,
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
