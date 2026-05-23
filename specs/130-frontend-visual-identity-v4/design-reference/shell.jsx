// App shell — composes Sidebar + main + Dock

function AppShell({ theme, active, dockActive = "contexto", children, withDock = true }) {
  return (
    <div
      style={{
        ...themeVars(theme),
        width: "100%",
        height: "100%",
        display: "flex",
        overflow: "hidden",
        fontFamily: "var(--font-text)",
        fontSize: 13,
      }}
    >
      <Sidebar theme={theme} active={active} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, position: "relative" }}>
        {children}
      </div>
      {withDock && <Dock active={dockActive} />}
    </div>
  );
}

// Tokens reference card — brand-aligned
function TokensReference({ theme }) {
  const swatches = [
    { name: "ember", value: theme.ember, mono: "#f7931e", role: "primary · ações, foco, JUDITE" },
    { name: "amethyst", value: theme.amethyst, mono: "#7800ff", role: "secondary · destaques pontuais" },
    { name: "azure", value: theme.azure, mono: "#15bddc", role: "info · dados, links" },
    { name: "ember-soft", value: theme.emberSoft, mono: "#bd6c0e", role: "ember escuro · sombra" },
    { name: "amethyst-soft", value: theme.amethystSoft, mono: "#5a16a6", role: "amethyst escuro" },
    { name: "azure-soft", value: theme.azureSoft, mono: "#0b8196", role: "azure escuro" },
  ];

  const neutrals = [
    { name: "bg", value: theme.bg, mono: "--bg", role: "fundo principal" },
    { name: "bg-ink", value: theme.bgInk, mono: "--bg-ink", role: "fundo profundo · sidebar" },
    { name: "bg-card", value: theme.bgCard, mono: "--bg-card", role: "cartões, chips" },
    { name: "line", value: theme.line, mono: "--line", role: "bordas estruturais" },
    { name: "text", value: theme.text, mono: "--text", role: "texto principal" },
    { name: "muted", value: theme.muted, mono: "--muted", role: "texto secundário" },
  ];

  return (
    <div
      style={{
        ...themeVars(theme),
        width: "100%",
        height: "100%",
        padding: "32px 40px",
        overflow: "auto",
        fontFamily: "var(--font-text)",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28, gap: 24 }}>
        <div>
          <Mono size={11} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.2em" }}>
            sistema · brand-aligned
          </Mono>
          <h2
            style={{
              margin: "10px 0 0",
              fontFamily: "var(--font-display)",
              fontSize: 36,
              fontWeight: 400,
              letterSpacing: "0.005em",
              textTransform: "uppercase",
              color: "var(--text)",
              lineHeight: 1.0,
            }}
          >
            Os tokens da forja
          </h2>
          <p style={{ margin: "10px 0 0", fontSize: 13.5, color: "var(--muted)", lineHeight: 1.55, maxWidth: 540 }}>
            Cores e tipografia do manual de ID Visual — aplicadas ao produto digital. Laranja brasa como foco, roxo e ciano como apoio.
          </p>
        </div>
        <BrandSymbol size={56} />
      </div>

      {/* Type */}
      <div style={{ marginBottom: 36 }}>
        <SectionHead>Tipografia</SectionHead>
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 24, alignItems: "start" }}>
          <div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 4 }}>
              <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>display</Mono>
              <Mono size={11} color="var(--ember)">Lilita One</Mono>
            </div>
            <div
              style={{
                fontFamily: "var(--font-display)",
                fontSize: 64,
                fontWeight: 400,
                letterSpacing: "0.005em",
                textTransform: "uppercase",
                lineHeight: 0.95,
                color: "var(--text)",
              }}
            >
              Forja a<br />
              <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", textTransform: "lowercase", color: "var(--ember)", letterSpacing: "-0.01em" }}>verdade</span>.
            </div>
            <div style={{ marginTop: 22, fontSize: 14, color: "var(--text-soft)", lineHeight: 1.65 }}>
              <strong style={{ color: "var(--text)", fontWeight: 600 }}>Corpo · Inter.</strong> Texto corrido, UI, descrições. Geometric sans neutra que casa com o display sem competir.
            </div>
            <div style={{ marginTop: 12, fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-soft)", lineHeight: 1.6 }}>
              mono · JetBrains Mono<br />
              <span style={{ color: "var(--faint)" }}>// dados, labels, timestamps, código</span>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <TypeRow size={28} family="var(--font-display)" label="display · 28" upper letterSpacing="0.01em" sample="Pipeline RAG no Postgres" />
            <TypeRow size={20} weight={600} label="h2 · 20" sample="Bases ativas" />
            <TypeRow size={15} weight={500} label="h3 · 15" sample="RAG · documentação pessoal" />
            <TypeRow size={13} weight={400} label="body · 13" sample="JUDITE coordena especialistas conforme a tarefa." />
            <TypeRow size={12} weight={400} label="meta · 12" muted sample="gpt-4o · 1.2s · 480 tok" />
            <TypeRow size={10} family="var(--font-mono)" label="mono · 10" muted sample="CONVERSA · INICIADA ÀS 12:42" upper />
            <TypeRow size={22} family="var(--font-serif)" italic label="acento · serif" sample="forja-se" />
          </div>
        </div>
      </div>

      {/* Brand colors */}
      <div style={{ marginBottom: 28 }}>
        <SectionHead>Cores · institucionais</SectionHead>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
          {swatches.slice(0, 3).map((s) => (
            <BigSwatch key={s.name} {...s} />
          ))}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginTop: 12 }}>
          {swatches.slice(3).map((s) => (
            <SmallSwatch key={s.name} {...s} />
          ))}
        </div>
      </div>

      {/* Neutrals */}
      <div style={{ marginBottom: 36 }}>
        <SectionHead>Neutros · superfícies</SectionHead>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 8 }}>
          {neutrals.map((s) => (
            <SmallSwatch key={s.name} {...s} />
          ))}
        </div>
      </div>

      {/* Components */}
      <div>
        <SectionHead>Primitivos</SectionHead>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
          <PrimitiveCard label="Chips · Contexto">
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              <Chip label="Agente" value="JUDITE" dot />
              <Chip label="Projeto" value="Forja" />
              <Chip label="Bases" value="2 ativas" />
            </div>
          </PrimitiveCard>
          <PrimitiveCard label="Tags · Tom">
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              <Tag tone="ember"><Pulse color="var(--ember)" size={4} /> ativa</Tag>
              <Tag tone="ok">indexado</Tag>
              <Tag tone="warn">atenção</Tag>
              <Tag tone="neutral">draft</Tag>
            </div>
          </PrimitiveCard>
          <PrimitiveCard label="Ações">
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <PrimaryButton icon="plus" label="Nova base" />
              <GhostButton icon="filter" label="Filtrar" />
            </div>
          </PrimitiveCard>
          <PrimitiveCard label="Identidade · JUDITE">
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Avatar kind="judite" size={32} theme={theme} />
              <div style={{ lineHeight: 1.1 }}>
                <div style={{ fontFamily: "var(--font-display)", fontSize: 14, color: "var(--text)", letterSpacing: "0.02em", textTransform: "uppercase" }}>JUDITE</div>
                <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 4 }}>
                  <Pulse color="var(--ok)" size={5} />
                  <Mono size={10} color="var(--muted)">online · gpt-4o</Mono>
                </div>
              </div>
            </div>
          </PrimitiveCard>
          <PrimitiveCard label="Inline KBD">
            <div style={{ fontSize: 12, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6 }}>
              pressione <KBD>⌘</KBD> + <KBD>K</KBD> para buscar
            </div>
          </PrimitiveCard>
          <PrimitiveCard label="Raio · Sombra">
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <div style={{ width: 50, height: 50, borderRadius: theme.radiusSm, background: "var(--bg-card)", border: "1px solid var(--line)" }} />
              <div style={{ width: 50, height: 50, borderRadius: theme.radius, background: "var(--bg-card)", border: "1px solid var(--line)", boxShadow: "var(--shadow-soft)" }} />
              <div style={{ width: 50, height: 50, borderRadius: theme.radiusLg, background: "var(--bg-card)", border: "1px solid color-mix(in srgb, var(--ember) 30%, var(--line))" }} />
              <Mono size={9.5} color="var(--faint)">
                {theme.radiusSm} · {theme.radius} · {theme.radiusLg}
              </Mono>
            </div>
          </PrimitiveCard>
        </div>
      </div>
    </div>
  );
}

function BigSwatch({ name, value, mono, role }) {
  return (
    <div style={{ borderRadius: "var(--radius)", overflow: "hidden", border: "1px solid var(--line-soft)", background: "var(--bg-card)" }}>
      <div style={{ height: 90, background: value, position: "relative" }}>
        <Mono size={9.5} color="rgba(0,0,0,0.55)" style={{ position: "absolute", top: 10, left: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.14em" }}>
          {mono}
        </Mono>
      </div>
      <div style={{ padding: "12px 14px" }}>
        <div style={{ fontFamily: "var(--font-display)", fontSize: 14, color: "var(--text)", textTransform: "uppercase", letterSpacing: "0.02em" }}>{name}</div>
        <Mono size={10} color="var(--muted)" style={{ marginTop: 4, display: "block" }}>
          {role}
        </Mono>
      </div>
    </div>
  );
}

function SmallSwatch({ name, value, mono, role }) {
  return (
    <div style={{ borderRadius: "var(--radius-sm)", overflow: "hidden", border: "1px solid var(--line-soft)" }}>
      <div style={{ height: 48, background: value }} />
      <div style={{ padding: "8px 10px", background: "var(--bg-card)" }}>
        <Mono size={10} color="var(--text)" style={{ fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em" }}>
          {name}
        </Mono>
        <Mono size={9.5} color="var(--muted)" style={{ marginTop: 2, display: "block" }}>
          {mono}
        </Mono>
        {role && (
          <Mono size={9} color="var(--faint)" style={{ marginTop: 2, display: "block" }}>
            {role}
          </Mono>
        )}
      </div>
    </div>
  );
}

function SectionHead({ children }) {
  return (
    <div style={{ marginBottom: 14, display: "flex", alignItems: "center", gap: 10 }}>
      <Mono size={11} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.18em" }}>
        {children}
      </Mono>
      <span style={{ flex: 1, height: 1, background: "var(--line-soft)" }} />
    </div>
  );
}

function TypeRow({ label, sample, size, weight = 400, family = "var(--font-text)", italic = false, muted = false, upper = false, letterSpacing }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "80px 1fr", alignItems: "baseline", gap: 16, padding: "5px 0" }}>
      <Mono size={9.5} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.1em" }}>
        {label}
      </Mono>
      <div
        style={{
          fontFamily: family,
          fontSize: size,
          fontWeight: weight,
          fontStyle: italic ? "italic" : "normal",
          color: muted ? "var(--muted)" : "var(--text)",
          letterSpacing: letterSpacing || (size >= 24 ? "0" : 0),
          textTransform: upper ? "uppercase" : "none",
          lineHeight: 1.15,
        }}
      >
        {sample}
      </div>
    </div>
  );
}

function PrimitiveCard({ label, children }) {
  return (
    <div style={{ padding: 16, borderRadius: "var(--radius)", background: "var(--bg-card)", border: "1px solid var(--line-soft)" }}>
      <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: 12, display: "block" }}>
        {label}
      </Mono>
      <div>{children}</div>
    </div>
  );
}

Object.assign(window, { AppShell, TokensReference });
