import type { ReactNode } from "react";

import { Mono } from "../../components/ui/Mono";

/**
 * Chrome compartilhado dos dashboards no re-skin v4 "Hearth".
 *
 * Mantém os 4 dashboards (Agentes/Projetos/Bases/Arquivos) coerentes com o frame
 * `design-reference/dashboards.jsx`: cabeçalho de seção tipográfico, glifos com
 * gradiente para entidades coloridas e selo de tipo de arquivo. Só apresentação —
 * nenhum dado é inventado; quem chama passa contagens e cores reais.
 */

/** Cabeçalho de seção v4: eyebrow mono + título em display (uppercase) + ações à direita. */
export function DashboardSectionHeader({
  eyebrow,
  title,
  children
}: {
  eyebrow: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col justify-between gap-3 border-b border-forge-line pb-4 sm:flex-row sm:items-end">
      <div className="min-w-0">
        <Mono size={10} className="block uppercase tracking-[0.16em] text-forge-faint">
          {eyebrow}
        </Mono>
        <h3 className="mt-1.5 truncate font-display text-2xl uppercase leading-none tracking-[0.015em] text-forge-text">
          {title}
        </h3>
      </div>
      {children && <div className="flex flex-shrink-0 flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

/**
 * Glifo quadrado com gradiente da cor da entidade (projeto, base, agente). Aceita
 * um ícone ou um rótulo curto (ex.: inicial). Decorativo (`aria-hidden`).
 */
export function GradientGlyph({
  color,
  label,
  icon,
  size = 36
}: {
  color: string;
  label?: string;
  icon?: ReactNode;
  size?: number;
}) {
  return (
    <span
      aria-hidden
      className="inline-flex flex-shrink-0 items-center justify-center rounded-sm font-display uppercase leading-none text-forge-ink-deep"
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.46),
        background: `linear-gradient(155deg, ${color}, color-mix(in srgb, ${color} 30%, var(--bg-ink)))`,
        border: `1px solid color-mix(in srgb, ${color} 30%, var(--line))`
      }}
    >
      {icon ?? label}
    </span>
  );
}

const FILE_TYPE_COLORS: Record<string, string> = {
  sql: "var(--azure)",
  json: "var(--azure)",
  png: "#5acf8c",
  jpg: "#5acf8c",
  jpeg: "#5acf8c",
  gif: "#5acf8c",
  webp: "#5acf8c",
  svg: "#5acf8c",
  avif: "#5acf8c",
  md: "var(--ember)",
  markdown: "var(--ember)",
  html: "var(--ember)",
  csv: "var(--amethyst)",
  pdf: "var(--err)",
  txt: "var(--muted)",
  fbx: "var(--amethyst)",
  obj: "var(--amethyst)",
  stl: "var(--amethyst)",
  glb: "var(--amethyst)",
  gltf: "var(--amethyst)"
};

function fileExtension(filename: string): string {
  const match = /\.([a-z0-9]+)$/i.exec(filename.trim());
  return match ? match[1].toLowerCase() : "";
}

/** Selo de tipo de arquivo: extensão em 3 letras, tingida pela categoria. Decorativo. */
export function FileGlyph({ filename, size = 28 }: { filename: string; size?: number }) {
  const ext = fileExtension(filename);
  const color = FILE_TYPE_COLORS[ext] ?? "var(--muted)";
  const label = (ext || "·").toUpperCase().slice(0, 3);
  return (
    <span
      aria-hidden
      className="inline-flex flex-shrink-0 items-center justify-center rounded-sm bg-forge-chip font-mono font-semibold"
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.32),
        color,
        border: `1px solid color-mix(in srgb, ${color} 30%, transparent)`
      }}
    >
      {label}
    </span>
  );
}
