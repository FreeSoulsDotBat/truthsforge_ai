/**
 * Cor estável para glifos de entidades sem cor própria (ex.: agentes), no re-skin v4.
 * Mantido fora de `dashboard-chrome.tsx` para o arquivo de componentes só exportar
 * componentes (regra `react-refresh/only-export-components`).
 */
const GLYPH_PALETTE = ["var(--ember)", "var(--amethyst)", "var(--azure)", "#5acf8c"] as const;

/** Cor determinística a partir de uma chave (id/nome). */
export function glyphColorForKey(key: string): string {
  let hash = 0;
  for (let index = 0; index < key.length; index += 1) {
    hash = (hash * 31 + key.charCodeAt(index)) | 0;
  }
  return GLYPH_PALETTE[Math.abs(hash) % GLYPH_PALETTE.length];
}
