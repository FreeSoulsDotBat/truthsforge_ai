// v4 — Fundamentos · sistema canônico de tokens
// Declara — sem comparações. Esta é a verdade única.

const TOKEN_MAP = [
  { tailwind: "forge-ink",        cssvar: "--bg",         hex: "#0c0d0f",                  use: "Fundo da aplicação (canvas)" },
  { tailwind: "forge-panel",      cssvar: "--bg-card",    hex: "#171716",                  use: "Cards, painéis, inputs preenchidos" },
  { tailwind: "forge-elev",       cssvar: "--bg-elev",    hex: "oklch(.195 .015 50)",      use: "Superfícies elevadas (spec cards)" },
  { tailwind: "forge-ink-deep",   cssvar: "--bg-ink",     hex: "oklch(.105 .012 45)",      use: "Poços encaixados, blocos de código" },
  { tailwind: "forge-line",       cssvar: "--line",       hex: "#313334",                  use: "Limites estruturais (sidebar, modal)" },
  { tailwind: "forge-line-soft",  cssvar: "--line-soft",  hex: "oklch(.25 .014 48)",       use: "Cards, divisores, grids internos" },
  { tailwind: "forge-text",       cssvar: "--text",       hex: "#e7edf5",                  use: "Texto primário" },
  { tailwind: "forge-text-soft",  cssvar: "--text-soft",  hex: "oklch(.84 .020 70)",       use: "Texto secundário, body copy" },
  { tailwind: "forge-muted",      cssvar: "--muted",      hex: "#a2a09a",                  use: "Labels, metadados, placeholders" },
  { tailwind: "forge-faint",      cssvar: "--faint",      hex: "oklch(.46 .018 60)",       use: "Eyebrows, baixíssima ênfase" },
  { tailwind: "forge-amber",      cssvar: "--ember",      hex: "#f7931e",                  use: "Marca primária — ember (calor da forja)" },
  { tailwind: "forge-amber-soft", cssvar: "--ember-soft", hex: "#bd6c0e",                  use: "Hover/active dos elementos ember" },
  { tailwind: "forge-amethyst",   cssvar: "--amethyst",   hex: "#7800ff",                  use: "Marca secundária (3D, multi-agente)" },
  { tailwind: "forge-blue",       cssvar: "--azure",      hex: "#15bddc",                  use: "Info, dados, links" },
  { tailwind: "forge-green",      cssvar: "--ok",         hex: "#62d98b",                  use: "Sucesso, ok, indexado" },
  { tailwind: "forge-red",        cssvar: "--err",        hex: "#ff6b6b",                  use: "Erro, destrutivo, bloqueado" },
  { tailwind: "forge-amber",      cssvar: "--warn",       hex: "#f7931e",                  use: "Aviso (alias de ember)" },
];

function Swatch({ hex, varName }) {
  // Render an actual swatch using the CSS var (works for oklch & hex alike)
  return (
    <div style={{
      width: 22, height: 22, borderRadius: 6, flexShrink: 0,
      background: `var(${varName})`,
      border: "1px solid color-mix(in srgb, var(--text) 14%, transparent)",
      boxShadow: "inset 0 0 0 1px rgba(0,0,0,0.25)",
    }} />
  );
}

function TokenMapTable() {
  return (
    <div style={{ borderRadius: "var(--radius)", border: "1px solid var(--line-soft)", overflow: "hidden", background: "var(--bg-elev)" }}>
      <div style={{ display: "grid", gridTemplateColumns: "44px 1.1fr 1.1fr 1.3fr 2.4fr", padding: "10px 14px", background: "var(--bg-ink)", borderBottom: "1px solid var(--line-soft)", gap: 10 }}>
        {["", "Tailwind", "CSS var", "Hex / valor", "Uso"].map((h, i) => (
          <Mono key={i} size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>{h}</Mono>
        ))}
      </div>
      {TOKEN_MAP.map((row, i) => (
        <div key={i} style={{
          display: "grid", gridTemplateColumns: "44px 1.1fr 1.1fr 1.3fr 2.4fr",
          padding: "9px 14px", alignItems: "center", gap: 10,
          borderTop: i ? "1px solid var(--line-soft)" : "none",
          background: i % 2 === 0 ? "transparent" : "color-mix(in srgb, var(--bg-ink) 35%, transparent)",
        }}>
          <Swatch varName={row.cssvar} />
          <Mono size={11} color="var(--azure)">{row.tailwind}</Mono>
          <Mono size={11} color="var(--ember)">{row.cssvar}</Mono>
          <Mono size={10.5} color="var(--text-soft)">{row.hex}</Mono>
          <span style={{ fontSize: 12, color: "var(--text-soft)", lineHeight: 1.5 }}>{row.use}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Specs canônicas — declaradas, não comparadas ───────────────────────────

const FOUNDATION_SPECS = [
  {
    id: "fnd-aside",
    name: "ContextAside",
    summary: "Painel direito tabbed. Largura fixa 360px (≥lg). Em <lg vira drawer fullscreen. Header com 5 PanelButtons em row; body em PanelStack vertical com scroll.",
    summaryEn: "Right-side tabbed aside. 360px fixed (≥lg), fullscreen drawer below. Header is a row of 5 PanelButtons; body is a vertical PanelStack with scroll.",
    rows: [
      ["width", "360px"],
      ["token", "--w-context-panel"],
      ["tabs", "context · history · audit · prompts · config"],
      ["breakpoint", "drawer fullscreen <lg"],
    ],
  },
  {
    id: "fnd-avatar",
    name: "Avatar JUDITE",
    summary: "Gradiente ember 135° + letra J em Lilita One. Pulse opcional ao lado quando streaming. Aparece em toda MessageBubble e no SidebarFooter.",
    summaryEn: "135° ember gradient + Lilita-One J. Optional pulse beside it while streaming. Used in every MessageBubble and the SidebarFooter.",
    rows: [
      ["size · chat", "32px"],
      ["size · sidebar", "24px"],
      ["fill", "linear-gradient(135°, var(--ember), var(--ember-soft))"],
      ["streaming", "pulse dot ember adjacent"],
    ],
  },
  {
    id: "fnd-composer",
    name: "Composer pill",
    summary: "Container do composer com border-radius 18px (--radius-lg). Padding interno 14px. Background bg-card. Border line-soft. Foco interno → glow ember sutil.",
    summaryEn: "Composer container: 18px radius, 14px inner padding, bg-card, line-soft border. Inner focus emits a subtle ember glow.",
    rows: [
      ["radius", "18px (--radius-lg)"],
      ["padding", "14px"],
      ["background", "var(--bg-card)"],
      ["border", "1px solid var(--line-soft)"],
      ["focus glow", "0 0 0 3px color-mix(ember 18%, transparent)"],
    ],
  },
  {
    id: "fnd-type",
    name: "Type stack",
    summary: "Quatro famílias com papéis distintos. Display em ALL CAPS para títulos grandes; serif itálico como acento warm; Inter como leitor principal; mono para metadados e código.",
    summaryEn: "Four families with distinct roles. Display ALL CAPS for big titles; italic serif as a warm accent; Inter for body; mono for metadata and code.",
    rows: [
      ["display", "Lilita One · uppercase"],
      ["text",    "Inter 300–700"],
      ["serif",   "Instrument Serif · italic accent"],
      ["mono",    "JetBrains Mono 400–600"],
    ],
  },
  {
    id: "fnd-borders",
    name: "Bordas",
    summary: "Dois tons, dois papéis. forge-line marca limites estruturais; forge-line-soft separa internamente. Hex inline em borders é proibido — sempre token.",
    summaryEn: "Two shades, two roles. forge-line for structure; forge-line-soft for inner separation. Inline hex in borders is banned — always token.",
    rows: [
      ["estrutura",  "var(--line) · sidebar edge, modal frame"],
      ["interno",    "var(--line-soft) · cards, divisores"],
      ["proibido",   "border-[#…] inline"],
    ],
  },
];

function FoundationCard({ spec }) {
  return (
    <div style={{ marginBottom: 18, borderRadius: "var(--radius)", border: "1px solid var(--line-soft)", background: "var(--bg-elev)", overflow: "hidden" }}>
      <div style={{ padding: "16px 18px 14px", borderBottom: "1px solid var(--line-soft)" }}>
        <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.18em", display: "block", marginBottom: 6 }}>
          canônico
        </Mono>
        <h4 style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 400, letterSpacing: "0.015em", textTransform: "uppercase", color: "var(--text)" }}>
          {spec.name}
        </h4>
        <p style={{ margin: "8px 0 0", fontSize: 13.5, color: "var(--text-soft)", lineHeight: 1.65 }}>{spec.summary}</p>
        <p style={{ margin: "4px 0 0", fontFamily: "var(--font-serif)", fontStyle: "italic", color: "var(--muted)", fontSize: 13, lineHeight: 1.6 }}>{spec.summaryEn}</p>
      </div>
      <div style={{ padding: "12px 18px", display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 18, rowGap: 6 }}>
        {spec.rows.map(([k, v], i) => (
          <React.Fragment key={i}>
            <Mono size={10.5} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>{k}</Mono>
            <Mono size={11.5} color="var(--ember)">{v}</Mono>
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

function V4_FoundationsSection() {
  return (
    <DocSection
      id="foundations"
      eyebrow="02 · Fundamentos"
      title="O sistema, declarado"
      intro="Tokens, tipografia e specs canônicas. Esta seção não compara, não migra, não debate — declara. Quando um item aparecer em conflito no produto, esta página vence."
    >
      <DocPara>
        <strong style={{ color: "var(--text)" }}>Fonte única da verdade.</strong> Sempre que produto e doc-site coexistirem, cada token tem duas formas — uma <TKN>forge-*</TKN> para Tailwind (web/src) e uma <TKN>--var</TKN> para CSS-in-JS (manual, mocks). A tabela abaixo é a referência mestre.
      </DocPara>

      <DocH4 id="token-map">Cores · Tailwind ↔ CSS vars</DocH4>
      <TokenMapTable />

      <DocCallout tone="ember" icon="flame" title="Calor primeiro">
        A paleta gira em torno de <strong style={{ color: "var(--text)" }}>ember</strong> (<TKN>#f7931e</TKN>) — o laranja da forja. Pretos warm em oklch (chroma .012–.015, hue ≈45°), brancos warm com toque dourado. Saturações altas só em ações pontuais (ember, amethyst, azure, ok, err). Tudo em volta respira em tons quentes.
      </DocCallout>

      <DocH4 id="canon-specs" style={{ marginTop: 32 }}>Specs canônicas</DocH4>
      <DocPara>
        Cinco peças com geometria fixa. Estas são as medidas oficiais — qualquer divergência em produção é bug, não variação.
      </DocPara>

      {FOUNDATION_SPECS.map((s) => <FoundationCard key={s.id} spec={s} />)}
    </DocSection>
  );
}

Object.assign(window, { V4_FoundationsSection, TOKEN_MAP });
