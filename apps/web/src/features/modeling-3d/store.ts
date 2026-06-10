import { create } from "zustand";

import type { ModelingSoftware } from "./types";

// RF-001: a preferência de software é parte da identidade dos próximos chats
// 3D ("Esta seção define o adapter preferido para próximos chats 3D" —
// Modeling3DSettingsSection). Persistida em localStorage para sobreviver a
// novo chat e a reload; `nextChatIs3D`/modais seguem transientes.
const SOFTWARE_STORAGE_KEY = "tf.modeling3d.software";

function loadStoredSoftware(): ModelingSoftware {
  try {
    const value = window.localStorage.getItem(SOFTWARE_STORAGE_KEY);
    if (value === "auto" || value === "blender" || value === "fusion") return value;
  } catch {
    // SSR/teste sem localStorage: cai no default.
  }
  return "auto";
}

function storeSoftware(value: ModelingSoftware): void {
  try {
    window.localStorage.setItem(SOFTWARE_STORAGE_KEY, value);
  } catch {
    // Persistência é best-effort.
  }
}

type Modeling3DStore = {
  nextChatIs3D: boolean;
  software: ModelingSoftware;
  diagnosticsOpen: boolean;
  enableDialogOpen: boolean;
  setNextChatIs3D: (value: boolean | ((current: boolean) => boolean)) => void;
  setSoftware: (value: ModelingSoftware) => void;
  setDiagnosticsOpen: (value: boolean) => void;
  setEnableDialogOpen: (value: boolean) => void;
  enableNextChat: () => void;
  disableNextChat: () => void;
  resetForNewChat: () => void;
};

export const useModeling3DStore = create<Modeling3DStore>((set) => ({
  nextChatIs3D: false,
  software: loadStoredSoftware(),
  diagnosticsOpen: false,
  enableDialogOpen: false,
  setNextChatIs3D: (value) =>
    set((state) => ({
      nextChatIs3D: typeof value === "function" ? value(state.nextChatIs3D) : value
    })),
  setSoftware: (software) => {
    storeSoftware(software);
    set({ software });
  },
  setDiagnosticsOpen: (diagnosticsOpen) => set({ diagnosticsOpen }),
  setEnableDialogOpen: (enableDialogOpen) => set({ enableDialogOpen }),
  enableNextChat: () => set({ nextChatIs3D: true }),
  disableNextChat: () => set({ nextChatIs3D: false }),
  resetForNewChat: () =>
    // NÃO zera `software`: a preferência configurada vale para os PRÓXIMOS
    // chats 3D (era descartada silenciosamente a cada novo chat).
    set({
      nextChatIs3D: false,
      diagnosticsOpen: false,
      enableDialogOpen: false
    })
}));
