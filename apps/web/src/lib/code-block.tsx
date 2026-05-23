import { useState } from "react";

/**
 * Bloco de código v4 (frame chat.jsx · CodeBlock): cabeçalho com a linguagem +
 * "copiar" e numeração de linhas. Em arquivo próprio para o módulo de markdown
 * seguir exportando só funções utilitárias (react-refresh).
 */
export function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const [copied, setCopied] = useState(false);
  const codeLines = code.split("\n");
  return (
    <div className="mb-3 mt-1 overflow-hidden rounded-sm border border-forge-line-soft bg-forge-ink-deep">
      <div className="flex items-center justify-between border-b border-forge-line-soft px-3 py-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-forge-faint">{lang || "código"}</span>
        <button
          type="button"
          className="font-mono text-[10px] text-forge-faint transition hover:text-forge-amber"
          onClick={() => {
            void navigator.clipboard?.writeText(code);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? "copiado" : "copiar"}
        </button>
      </div>
      <div className="overflow-x-auto px-3.5 py-2.5 font-mono text-xs leading-[1.7] text-forge-text-soft">
        {codeLines.map((codeLine, lineIndex) => (
          <div key={lineIndex} className="flex gap-3.5">
            <span className="w-4 shrink-0 select-none text-right text-forge-faint">{lineIndex + 1}</span>
            <span className="whitespace-pre">{codeLine}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
