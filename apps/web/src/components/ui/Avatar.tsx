import { User } from "lucide-react";

import { cn } from "../../lib/utils";

interface AvatarProps {
  /** `judite` = marca (gradiente ember + J Lilita One); `user` = genérico. */
  kind?: "user" | "judite";
  size?: number;
  className?: string;
}

/** Avatar da conversa. JUDITE usa a marca ember; usuário usa ícone neutro. */
export function Avatar({ kind = "user", size = 26, className }: AvatarProps) {
  if (kind === "judite") {
    return (
      <span
        className={cn("relative inline-flex shrink-0 items-center justify-center rounded-full font-display", className)}
        style={{
          width: size,
          height: size,
          color: "var(--ember-ink)",
          background:
            "radial-gradient(circle at 30% 30%, var(--ember), color-mix(in srgb, var(--ember) 40%, var(--bg-ink)))",
          boxShadow: "0 0 0 1px color-mix(in srgb, var(--ember) 35%, transparent), 0 8px 22px -10px var(--ember-glow)"
        }}
        aria-label="JUDITE"
      >
        <span style={{ fontSize: size * 0.5, letterSpacing: "0.02em" }}>J</span>
      </span>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full border border-forge-line-soft bg-forge-chip text-forge-muted",
        className
      )}
      style={{ width: size, height: size }}
      aria-label="Usuário"
    >
      <User size={size * 0.5} strokeWidth={1.75} />
    </span>
  );
}
