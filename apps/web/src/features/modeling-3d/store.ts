import { create } from "zustand";

import type { ModelingSoftware } from "./types";

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
  software: "auto",
  diagnosticsOpen: false,
  enableDialogOpen: false,
  setNextChatIs3D: (value) =>
    set((state) => ({
      nextChatIs3D: typeof value === "function" ? value(state.nextChatIs3D) : value
    })),
  setSoftware: (software) => set({ software }),
  setDiagnosticsOpen: (diagnosticsOpen) => set({ diagnosticsOpen }),
  setEnableDialogOpen: (enableDialogOpen) => set({ enableDialogOpen }),
  enableNextChat: () => set({ nextChatIs3D: true }),
  disableNextChat: () => set({ nextChatIs3D: false }),
  resetForNewChat: () =>
    set({
      nextChatIs3D: false,
      software: "auto",
      diagnosticsOpen: false,
      enableDialogOpen: false
    })
}));
