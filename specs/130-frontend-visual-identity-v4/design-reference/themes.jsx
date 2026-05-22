// Truth's Forge AI — Brand-aligned theme (Hearth, cozy + warm)
// Palette from ID Visual manual: orange #f7931e primary, purple #7800ff secondary, cyan #15bddc tertiary.
// Fonts: Lilita One (display/títulos), Inter (body/UI), Instrument Serif (acento poético italico).

const HEARTH = {
  id: "hearth",
  name: "Hearth",
  tagline: "Onde se descansa, forja-se a verdade.",
  vibe: "Quente · brasa · marca aplicada",

  // Backgrounds — warm dark, near-black with subtle orange undertone
  bg: "oklch(0.155 0.014 50)",
  bgInk: "oklch(0.105 0.012 45)",
  bgElev: "oklch(0.195 0.015 50)",
  bgCard: "oklch(0.225 0.016 50)",
  bgChip: "oklch(0.21 0.014 50)",
  bgHover: "oklch(0.255 0.018 48)",

  // Lines — quiet
  line: "oklch(0.32 0.018 50)",
  lineSoft: "oklch(0.25 0.014 48)",

  // Text
  text: "oklch(0.96 0.012 75)",
  textSoft: "oklch(0.84 0.020 70)",
  muted: "oklch(0.64 0.018 65)",
  faint: "oklch(0.46 0.018 60)",

  // Brand colors — exact from manual
  // Ember / primary orange #f7931e
  ember: "#f7931e",
  emberSoft: "#bd6c0e", // brand dark orange
  emberInk: "#3a1f06",
  emberGlow: "rgba(247, 147, 30, 0.22)",

  // Secondary purple #7800ff (used SPARINGLY — JUDITE highlights, special states)
  amethyst: "#7800ff",
  amethystSoft: "#5a16a6", // brand dark purple
  amethystGlow: "rgba(120, 0, 255, 0.28)",

  // Tertiary cyan #15bddc (info / data / links)
  azure: "#15bddc",
  azureSoft: "#0b8196", // brand dark cyan
  azureGlow: "rgba(21, 189, 220, 0.22)",

  // Semantic
  ok: "#5acf8c",
  warn: "#f7931e", // ember doubles as warn
  err: "#ff5a4a",

  // Type — brand stack
  fontDisplay: "'Lilita One', 'Inter', ui-sans-serif, system-ui, sans-serif",
  fontText: "'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif",
  fontSerif: "'Instrument Serif', 'Inter', serif",
  fontMono: "'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace",

  // Tone
  radius: "12px",
  radiusSm: "8px",
  radiusLg: "18px",
  shadowSoft: "0 1px 0 0 oklch(0.30 0.018 50 / 0.5), 0 24px 60px -24px oklch(0.05 0.005 50 / 0.7)",
  shadowGlow: "0 0 0 1px rgba(247, 147, 30, 0.20), 0 12px 36px -14px rgba(247, 147, 30, 0.35)",

  density: "calm",
};

function themeVars(t) {
  return {
    "--bg": t.bg,
    "--bg-ink": t.bgInk,
    "--bg-elev": t.bgElev,
    "--bg-card": t.bgCard,
    "--bg-chip": t.bgChip,
    "--bg-hover": t.bgHover,
    "--line": t.line,
    "--line-soft": t.lineSoft,
    "--text": t.text,
    "--text-soft": t.textSoft,
    "--muted": t.muted,
    "--faint": t.faint,
    "--ember": t.ember,
    "--ember-soft": t.emberSoft,
    "--ember-ink": t.emberInk,
    "--ember-glow": t.emberGlow,
    "--amethyst": t.amethyst,
    "--amethyst-soft": t.amethystSoft,
    "--amethyst-glow": t.amethystGlow,
    "--azure": t.azure,
    "--azure-soft": t.azureSoft,
    "--azure-glow": t.azureGlow,
    "--ok": t.ok,
    "--warn": t.warn,
    "--err": t.err,
    "--font-text": t.fontText,
    "--font-display": t.fontDisplay,
    "--font-serif": t.fontSerif,
    "--font-mono": t.fontMono,
    "--radius": t.radius,
    "--radius-sm": t.radiusSm,
    "--radius-lg": t.radiusLg,
    "--shadow-soft": t.shadowSoft,
    "--shadow-glow": t.shadowGlow,
    background: t.bg,
    color: t.text,
    fontFamily: t.fontText,
  };
}

Object.assign(window, { HEARTH, themeVars });
