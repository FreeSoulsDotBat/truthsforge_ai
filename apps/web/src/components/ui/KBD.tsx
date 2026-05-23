import type { HTMLAttributes } from "react";

import { cn } from "../../lib/utils";

/** Tecla de atalho (`⌘`, `Enter`, `Esc`). */
export function KBD({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <kbd
      className={cn(
        "inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[4px] px-[5px] font-mono text-[10px] text-forge-muted bg-forge-chip",
        className
      )}
      {...props}
    />
  );
}
