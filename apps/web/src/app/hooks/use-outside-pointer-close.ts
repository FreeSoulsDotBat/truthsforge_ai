import { useEffect } from "react";
import type { RefObject } from "react";

type OutsidePointerCloseConfig = {
  executionMenuRef: RefObject<HTMLDivElement | null>;
  shortcutMenuRef: RefObject<HTMLDivElement | null>;
  onCloseExecutionMenu: () => void;
  onCloseShortcutMenu: () => void;
};

export function useOutsidePointerClose({
  executionMenuRef,
  shortcutMenuRef,
  onCloseExecutionMenu,
  onCloseShortcutMenu
}: OutsidePointerCloseConfig): void {
  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (shortcutMenuRef.current && !shortcutMenuRef.current.contains(target)) {
        onCloseShortcutMenu();
      }
      if (executionMenuRef.current && !executionMenuRef.current.contains(target)) {
        onCloseExecutionMenu();
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [executionMenuRef, onCloseExecutionMenu, onCloseShortcutMenu, shortcutMenuRef]);
}
