import { ArrowUpRight, ChevronLeft, ChevronRight, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { KBD } from "../../../components/ui/KBD";
import { Mono } from "../../../components/ui/Mono";
import { cn } from "../../../lib/utils";

export interface ImagePreviewProps {
  urls: string[];
  className?: string;
}

// Refcount local de scroll-lock: vários ImagePreview podem abrir/fechar de forma
// independente; só removemos a classe global quando o último deles fecha, evitando
// que um preview destrave o body enquanto outro ainda está aberto.
let scrollLockCount = 0;
function lockBodyScroll() {
  scrollLockCount += 1;
  document.body.classList.add("overflow-hidden");
}
function unlockBodyScroll() {
  scrollLockCount = Math.max(0, scrollLockCount - 1);
  if (scrollLockCount === 0) document.body.classList.remove("overflow-hidden");
}

/**
 * Família ImagePreview v4 (frame image-preview.jsx): grade de imagens da
 * mensagem + lightbox em tela cheia. Clique abre; ← → navega; Esc fecha.
 *
 * Só usa dados reais (a URL e a posição na lista) — não inventa nome/dimensões/
 * tamanho como o mockup. Substitui o `<img>` plano no balão de mensagem.
 */
export function ImagePreview({ urls, className }: ImagePreviewProps) {
  const [index, setIndex] = useState<number | null>(null);
  const open = index !== null;
  const count = urls.length;

  const close = useCallback(() => setIndex(null), []);
  const go = useCallback(
    (delta: number) => setIndex((current) => (current === null ? current : (current + delta + count) % count)),
    [count]
  );

  useEffect(() => {
    if (!open) return undefined;
    lockBodyScroll();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
      else if (event.key === "ArrowRight") go(1);
      else if (event.key === "ArrowLeft") go(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      unlockBodyScroll();
      window.removeEventListener("keydown", onKey);
    };
  }, [open, close, go]);

  if (!count) return null;

  return (
    <>
      <div className={cn(count > 1 ? "grid grid-cols-2 gap-2" : "grid gap-2", className)}>
        {urls.map((url, i) => (
          <button
            key={url}
            type="button"
            onClick={() => setIndex(i)}
            className="group relative overflow-hidden rounded border border-forge-line-soft bg-forge-ink-deep shadow-soft transition hover:border-forge-amber/40"
            aria-label="Ampliar imagem"
          >
            <img src={url} alt="Prévia de imagem" loading="lazy" className="max-h-[420px] w-full object-contain" />
            <span className="absolute right-2 top-2 inline-flex h-6 w-6 items-center justify-center rounded-sm bg-black/55 text-white opacity-0 backdrop-blur-sm transition group-hover:opacity-100">
              <ArrowUpRight size={13} />
            </span>
          </button>
        ))}
      </div>

      {open && index !== null && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Visualizador de imagem"
          className="fixed inset-0 z-[90] flex flex-col bg-black/80 p-4"
          onClick={(event) => {
            if (event.target === event.currentTarget) close();
          }}
        >
          <div className="mx-auto flex w-full max-w-5xl items-center gap-3 px-1 py-2">
            <Mono size={10} className="text-forge-faint">
              {index + 1} / {count}
            </Mono>
            <span className="flex-1" />
            <a
              href={urls[index]}
              target="_blank"
              rel="noreferrer"
              className="font-mono text-[10px] text-forge-blue hover:underline"
            >
              abrir original
            </a>
            <button
              type="button"
              onClick={close}
              aria-label="Fechar visualizador"
              className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-white/20 text-white/80 transition hover:text-white"
            >
              <X size={14} />
            </button>
          </div>

          <div className="relative flex min-h-0 flex-1 items-center justify-center">
            {count > 1 && (
              <button
                type="button"
                onClick={() => go(-1)}
                aria-label="Imagem anterior"
                className="absolute left-2 inline-flex h-9 w-9 items-center justify-center rounded-full bg-black/55 text-white backdrop-blur-sm transition hover:bg-black/80"
              >
                <ChevronLeft size={18} />
              </button>
            )}
            <img src={urls[index]} alt="Imagem ampliada" className="max-h-full max-w-full rounded-md object-contain" />
            {count > 1 && (
              <button
                type="button"
                onClick={() => go(1)}
                aria-label="Próxima imagem"
                className="absolute right-2 inline-flex h-9 w-9 items-center justify-center rounded-full bg-black/55 text-white backdrop-blur-sm transition hover:bg-black/80"
              >
                <ChevronRight size={18} />
              </button>
            )}
          </div>

          <div className="mx-auto flex w-full max-w-5xl items-center gap-4 px-1 py-2">
            <Mono size={10} className="flex items-center gap-1.5 text-forge-faint">
              <KBD>←</KBD>
              <KBD>→</KBD>
              navegar
            </Mono>
            <Mono size={10} className="flex items-center gap-1.5 text-forge-faint">
              <KBD>esc</KBD>
              fechar
            </Mono>
          </div>
        </div>
      )}
    </>
  );
}
