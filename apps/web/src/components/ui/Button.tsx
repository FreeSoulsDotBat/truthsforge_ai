import type { ButtonHTMLAttributes } from "react";

import { cn } from "../../lib/utils";

export function Button({ className, type = "button", ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex h-10 items-center justify-center gap-2 rounded-md border border-forge-line bg-[#1a1d20] px-3 text-sm font-medium text-forge-text transition hover:bg-[#222a2f] disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}
