// Right panel expanded — Contexto detail view + tokens reference

function ContextPanel({ theme }) {
  return (
    <div
      style={{
        width: 400,
        height: "100%",
        background: "var(--bg-ink)",
        borderLeft: "1px solid var(--line-soft)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div style={{ padding: "20px 22px 18px", borderBottom: "1px solid var(--line-soft)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
          <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>
            painel · contexto
          </Mono>
          <Icon name="x" size={14} stroke="var(--muted)" />
        </div>
        <h2
          style={{
            margin: "8px 0 0",
            fontFamily: "var(--font-display)",
            fontSize: 19,
            fontWeight: 400,
            letterSpacing: "0.015em",
            textTransform: "uppercase",
            color: "var(--text)",
            lineHeight: 1.05,
          }}
        >
          O que JUDITE está olhando
        </h2>
        <p style={{ margin: "6px 0 0", fontSize: 12, color: "var(--muted)", lineHeight: 1.5 }}>
          Tudo que entra no prompt agora. Edite à vontade — JUDITE re-recupera ao próximo turno.
        </p>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "20px 22px", display: "flex", flexDirection: "column", gap: 22 }}>
        {/* Custo do turno */}
        <Section icon="gauge" title="Custos · turno atual">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <Stat label="entrada" value="2.1k" unit="tok" theme={theme} />
            <Stat label="saída" value="480" unit="tok" theme={theme} />
            <Stat label="latência" value="1.2s" theme={theme} />
            <Stat label="custo" value="R$ 0,043" theme={theme} ember />
          </div>
        </Section>

        {/* Bases ativas */}
        <Section icon="database" title="Bases ativas · 2">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <KBChip name="RAG · documentação pessoal" docs={124} active />
            <KBChip name="Estudos · sistemas distribuídos" docs={48} />
          </div>
        </Section>

        {/* Documentos citados */}
        <Section icon="file-text" title="Trechos citados · 4">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {[
              { title: "pgvector-runbook.md", chunk: "linha 24-58", score: 0.92 },
              { title: "schema-rag-v3.sql", chunk: "trecho 1/3", score: 0.88 },
              { title: "audit-tokens.md", chunk: "linha 12-30", score: 0.74 },
              { title: "indexes-hnsw.md", chunk: "linha 4-22", score: 0.71 },
            ].map((d, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: 8, background: "var(--bg-card)", border: "1px solid var(--line-soft)" }}>
                <Icon name="file-text" size={12} stroke="var(--muted)" />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: "var(--text)" }}>{d.title}</div>
                  <Mono size={10} color="var(--faint)">
                    {d.chunk}
                  </Mono>
                </div>
                <div style={{ textAlign: "right" }}>
                  <Mono size={10} color="var(--ember)">
                    {d.score.toFixed(2)}
                  </Mono>
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Modo de execução */}
        <Section icon="activity" title="Modo de execução">
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <ModeRow label="Raciocínio padrão" active />
            <ModeRow label="Resumo oficial" hint="OpenAI · só texto" />
            <ModeRow label="Pesquisa profunda" hint="2-8 min · até 30 chamadas" />
            <ModeRow label="Geração de imagem" hint="dall-e 3" />
            <ModeRow label="Multi-agente" hint="JUDITE + 2 apoios" />
            <ModeRow label="MCP 3D" hint="Blender · Fusion" />
          </div>
        </Section>
      </div>

      {/* Footer */}
      <div style={{ padding: "14px 22px", borderTop: "1px solid var(--line-soft)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Mono size={10} color="var(--faint)">
          atualizado há 4s
        </Mono>
        <Mono size={10} color="var(--muted)">
          <KBD>?</KBD> ajuda
        </Mono>
      </div>
    </div>
  );
}

function Section({ icon, title, children }) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <Icon name={icon} size={12} stroke="var(--ember)" />
        <Mono size={10.5} color="var(--text-soft)" style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>
          {title}
        </Mono>
      </div>
      {children}
    </div>
  );
}

function Stat({ label, value, unit, theme, ember }) {
  return (
    <div style={{ padding: "10px 12px", borderRadius: 8, background: "var(--bg-card)", border: "1px solid var(--line-soft)" }}>
      <Mono size={9.5} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>
        {label}
      </Mono>
      <div style={{ marginTop: 4, fontSize: 18, color: ember ? "var(--ember)" : "var(--text)", fontWeight: 400, fontFamily: "var(--font-display)", letterSpacing: "0.005em" }}>
        {value}
        {unit && <Mono size={10} color="var(--faint)" style={{ marginLeft: 4 }}>{unit}</Mono>}
      </div>
    </div>
  );
}

function KBChip({ name, docs, active }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", borderRadius: 8, background: active ? "color-mix(in oklch, var(--ember) 8%, var(--bg-card))" : "var(--bg-card)", border: active ? "1px solid color-mix(in oklch, var(--ember) 25%, transparent)" : "1px solid var(--line-soft)" }}>
      <span style={{ width: 6, height: 6, borderRadius: 2, background: active ? "var(--ember)" : "var(--muted)", transform: "rotate(45deg)", boxShadow: active ? "0 0 8px var(--ember-glow)" : "none" }} />
      <span style={{ flex: 1, fontSize: 12.5, color: "var(--text)" }}>{name}</span>
      <Mono size={10} color="var(--muted)">{docs} docs</Mono>
    </div>
  );
}

function ModeRow({ label, hint, active = false }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: 6, background: active ? "var(--bg-card)" : "transparent" }}>
      <span
        style={{
          width: 14,
          height: 14,
          borderRadius: 4,
          border: `1.5px solid ${active ? "var(--ember)" : "var(--line)"}`,
          background: active ? "var(--ember)" : "transparent",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {active && <Icon name="check" size={9} stroke="var(--ember-ink)" strokeWidth={3} />}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, color: active ? "var(--text)" : "var(--text-soft)" }}>{label}</div>
        {hint && (
          <Mono size={9.5} color="var(--faint)" style={{ marginTop: 1, display: "block" }}>
            {hint}
          </Mono>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { ContextPanel });
