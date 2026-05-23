import { X } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "../../lib/utils";
import { Mono } from "./Mono";

export type ModalAccent = "ember" | "amethyst" | "azure" | "danger";

const ACCENT: Record<ModalAccent, { color: string; glow: string }> = {
  ember: { color: "var(--ember)", glow: "var(--ember-glow)" },
  amethyst: { color: "var(--amethyst)", glow: "var(--amethyst-glow)" },
  azure: { color: "var(--azure)", glow: "var(--azure-glow)" },
  danger: { color: "var(--err)", glow: "rgba(255, 90, 74, 0.25)" }
};

export interface ModalShellProps {
  /** Rótulo curto mono acima do título (cor do acento). */
  eyebrow?: string;
  title: ReactNode;
  /** id do `<h2>` — para `aria-labelledby` do diálogo pai. */
  titleId?: string;
  accent?: ModalAccent;
  /** Renderiza o botão X de fechar (chama este callback). */
  onClose?: () => void;
  footer?: ReactNode;
  children?: ReactNode;
  /** Largura via classe Tailwind (ex.: "max-w-md", "max-w-lg"). */
  className?: string;
}

/**
 * Casca visual de modal v4 "Hearth" (frame modals.jsx · ModalShell): superfície
 * elevada, faixa de acento à esquerda, brilho do acento, cabeçalho com eyebrow
 * mono + título em display e um X opcional, corpo respirado e rodapé de ações.
 *
 * Apresentacional: NÃO gerencia backdrop, foco nem teclado — o diálogo pai
 * mantém `role`, focus-trap e Escape. Renderize esta casca dentro do backdrop.
 */
export function ModalShell({
  eyebrow,
  title,
  titleId,
  accent = "ember",
  onClose,
  footer,
  children,
  className
}: ModalShellProps) {
  const a = ACCENT[accent];
  return (
    <div
      className={cn("relative w-full overflow-hidden rounded-lg border border-forge-line bg-forge-elev", className)}
      style={{ boxShadow: `0 24px 80px -24px ${a.glow}` }}
    >
      <span
        aria-hidden
        className="absolute bottom-0 left-0 top-0 w-[3px]"
        style={{ background: a.color, boxShadow: `0 0 12px ${a.glow}` }}
      />
      <div className="flex items-start justify-between gap-4 border-b border-forge-line-soft px-6 py-5">
        <div className="min-w-0">
          {eyebrow && (
            <Mono size={10} className="uppercase tracking-[0.14em]" style={{ color: a.color }}>
              {eyebrow}
            </Mono>
          )}
          <h2
            id={titleId}
            className={cn(
              "font-display text-[22px] uppercase leading-tight tracking-[0.01em] text-forge-text",
              eyebrow && "mt-2"
            )}
          >
            {title}
          </h2>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-forge-line-soft text-forge-muted transition hover:text-forge-text"
          >
            <X size={13} />
          </button>
        )}
      </div>
      <div className="px-6 py-5">{children}</div>
      {footer && (
        <div className="flex flex-wrap justify-end gap-2 border-t border-forge-line-soft bg-forge-ink-deep/50 px-6 py-4">
          {footer}
        </div>
      )}
    </div>
  );
}
