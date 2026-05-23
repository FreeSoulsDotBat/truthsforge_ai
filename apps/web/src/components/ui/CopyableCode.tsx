import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { cn } from "../../lib/utils";

interface CopyableCodeProps {
  /** Conteúdo curto a copiar (trace IDs, hashes). Não usar para code blocks. */
  children: string;
  /** Descreve o que será copiado (a11y + title). */
  tip?: string;
  className?: string;
}

/** `<code>` inline copiável — clique ou Enter/Espaço copia, com confirmação breve. */
export function CopyableCode({ children, tip = "copiar", className }: CopyableCodeProps) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    if (!navigator.clipboard) return;
    void navigator.clipboard.writeText(children).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    });
  };

  return (
    <span
      role="button"
      tabIndex={0}
      aria-label={`Copiar ${tip}`}
      title={tip}
      onClick={copy}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          copy();
        }
      }}
      className={cn(
        "inline-flex cursor-pointer items-center gap-1.5 rounded-[4px] border border-forge-line-soft bg-forge-panel px-2 py-[3px] font-mono text-[11px] text-forge-text-soft",
        className
      )}
    >
      {children}
      {copied ? (
        <Check size={10} className="text-forge-green" aria-hidden />
      ) : (
        <Copy size={10} className="text-forge-faint" aria-hidden />
      )}
    </span>
  );
}
