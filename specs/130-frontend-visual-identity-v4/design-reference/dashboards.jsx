// Dashboard views — agents, projects/knowledge/files

function DashboardHeader({ theme, eyebrow, title, subtitle, action }) {
  return (
    <div style={{ padding: "26px 40px 22px", borderBottom: "1px solid var(--line-soft)", display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 20 }}>
      <div style={{ minWidth: 0, flex: 1 }}>
        <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.16em" }}>
          {eyebrow}
        </Mono>
        <h1
          style={{
            margin: "6px 0 0",
            fontFamily: "var(--font-display)",
            fontSize: 30,
            fontWeight: 400,
            letterSpacing: "0.015em",
            textTransform: "uppercase",
            color: "var(--text)",
            lineHeight: 1.0,
          }}
        >
          {title}
        </h1>
        {subtitle && (
          <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--muted)", lineHeight: 1.5, maxWidth: 560 }}>{subtitle}</p>
        )}
      </div>
      {action}
    </div>
  );
}

function PrimaryButton({ icon, label }) {
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        height: 36,
        padding: "0 14px",
        borderRadius: 10,
        background: "color-mix(in oklch, var(--ember) 14%, var(--bg-card))",
        border: "1px solid color-mix(in oklch, var(--ember) 30%, transparent)",
        color: "var(--text)",
        fontSize: 13,
        fontWeight: 500,
        boxShadow: "0 8px 24px -16px var(--ember-glow)",
      }}
    >
      {icon && <Icon name={icon} size={14} stroke="var(--ember)" />}
      {label}
    </div>
  );
}

function GhostButton({ icon, label }) {
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        height: 32,
        padding: "0 12px",
        borderRadius: 8,
        background: "var(--bg-card)",
        border: "1px solid var(--line-soft)",
        color: "var(--text-soft)",
        fontSize: 12.5,
      }}
    >
      {icon && <Icon name={icon} size={13} stroke="var(--muted)" />}
      {label}
    </div>
  );
}

function AgentDashboard({ theme }) {
  const agents = [
    { name: "JUDITE", role: "Orquestradora", desc: "Coordena especialistas, decide handoffs, mantém memória de longo prazo.", model: "gpt-4o", provider: "openai", tasks: 42, active: true, color: "var(--ember)" },
    { name: "CALÍOPE", role: "Pesquisadora", desc: "Deep research, leitura crítica, síntese cruzada de fontes.", model: "claude-3.7-sonnet", provider: "anthropic", tasks: 18, color: "var(--amethyst)" },
    { name: "FERRO", role: "Engenheira", desc: "Código, refactors, infra, scripts. Lê o repo antes de responder.", model: "gpt-4o · qwen-coder", provider: "local", tasks: 31, color: "var(--azure)" },
    { name: "ALBA", role: "Curadora", desc: "Rotulagem, RAG, organização de bases. Foco em recall.", model: "claude-3.5-haiku", provider: "anthropic", tasks: 9, color: "#5acf8c" },
    { name: "GROD", role: "Auditor", desc: "Verifica custos, latência, compliance. Avisa antes do limite.", model: "gpt-4o-mini", provider: "openai", tasks: 6, muted: true, color: "var(--muted)" },
    { name: "VIRA", role: "Tradutora", desc: "pt-BR ↔ EN, normaliza tom. Inativa hoje.", model: "—", provider: "—", tasks: 0, muted: true, color: "var(--muted)" },
  ];

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, background: "var(--bg)", overflow: "hidden" }}>
      <DashboardHeader
        theme={theme}
        eyebrow="AGENTES · 6 ATIVOS"
        title="O elenco da forja"
        subtitle="JUDITE delega para especialistas conforme a tarefa. Cada um tem seu modelo, seu prompt-mãe e suas bases. Você decide quando e como."
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <GhostButton icon="filter" label="Filtrar" />
            <PrimaryButton icon="plus" label="Novo agente" />
          </div>
        }
      />

      <div style={{ padding: "24px 40px", overflow: "auto", flex: 1 }}>
        {/* Quick stats */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 28 }}>
          {[
            { label: "Agentes ativos", value: "6", sub: "+1 esta semana" },
            { label: "Tokens · maio", value: "1.4M", sub: "↓ 12% vs abril" },
            { label: "Custo · maio", value: "R$ 12,84", sub: "6% do teto" },
            { label: "Handoffs", value: "84", sub: "via JUDITE" },
          ].map((s, i) => (
            <div key={i} style={{ padding: "14px 16px", borderRadius: "var(--radius)", background: "var(--bg-card)", border: "1px solid var(--line-soft)" }}>
              <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>
                {s.label}
              </Mono>
              <div style={{ marginTop: 8, fontSize: 26, fontWeight: 400, color: "var(--text)", letterSpacing: "0", fontFamily: "var(--font-display)" }}>
                {s.value}
              </div>
              <Mono size={10} color="var(--muted)" style={{ marginTop: 4, display: "block" }}>
                {s.sub}
              </Mono>
            </div>
          ))}
        </div>

        {/* Agent grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
          {agents.map((a, i) => (
            <AgentCard key={i} agent={a} theme={theme} />
          ))}
        </div>
      </div>
    </div>
  );
}

function AgentCard({ agent, theme }) {
  return (
    <div
      style={{
        padding: "18px 18px 14px",
        borderRadius: "var(--radius)",
        background: agent.active ? "color-mix(in oklch, var(--ember) 4%, var(--bg-card))" : "var(--bg-card)",
        border: agent.active ? "1px solid color-mix(in oklch, var(--ember) 22%, transparent)" : "1px solid var(--line-soft)",
        position: "relative",
        opacity: agent.muted ? 0.6 : 1,
        boxShadow: agent.active ? "0 12px 28px -22px var(--ember-glow)" : "none",
      }}
    >
      {agent.active && (
        <div style={{ position: "absolute", top: 14, right: 14 }}>
          <Tag tone="ember">
            <Pulse color="var(--ember)" size={4} /> ativa agora
          </Tag>
        </div>
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
        <div
          style={{
            width: 38,
            height: 38,
            borderRadius: 10,
            background: `linear-gradient(155deg, ${agent.color}, color-mix(in oklch, ${agent.color} 30%, var(--bg-ink)))`,
            border: `1px solid color-mix(in oklch, ${agent.color} 30%, var(--line))`,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--bg-ink)",
            fontFamily: "var(--font-display)",
            fontSize: 19,
            fontWeight: 400,
            letterSpacing: "0.01em",
          }}
        >
          {agent.name[0]}
        </div>
        <div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 17, fontWeight: 400, color: "var(--text)", letterSpacing: "0.02em", textTransform: "uppercase" }}>{agent.name}</div>
          <Mono size={10} color="var(--muted)" style={{ textTransform: "uppercase", letterSpacing: "0.1em" }}>
            {agent.role}
          </Mono>
        </div>
      </div>
      <div style={{ fontSize: 12.5, color: "var(--text-soft)", lineHeight: 1.5, marginBottom: 16, minHeight: 36 }}>{agent.desc}</div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 12, borderTop: "1px solid var(--line-soft)" }}>
        <div>
          <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.1em" }}>
            modelo
          </Mono>
          <div style={{ fontSize: 11.5, color: "var(--text-soft)", fontFamily: "var(--font-mono)", marginTop: 2 }}>{agent.model}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.1em" }}>
            tarefas · 30d
          </Mono>
          <div style={{ fontSize: 13, color: "var(--text)", fontWeight: 600, marginTop: 2 }}>{agent.tasks}</div>
        </div>
      </div>
    </div>
  );
}

function KnowledgeDashboard({ theme }) {
  const bases = [
    { name: "RAG · documentação pessoal", color: "var(--ember)", docs: 124, chunks: "3.4k", tags: ["pessoal", "notas"], updated: "2h", active: true },
    { name: "Estudos · sistemas distribuídos", color: "var(--amethyst)", docs: 48, chunks: "1.1k", tags: ["raft", "consenso", "papers"], updated: "1d" },
    { name: "Direito · jurisprudência", color: "var(--azure)", docs: 211, chunks: "8.9k", tags: ["stf", "stj"], updated: "4d" },
    { name: "Receitas e despensa", color: "#5acf8c", docs: 36, chunks: "420", tags: ["familia"], updated: "1sem" },
  ];

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, background: "var(--bg)", overflow: "hidden" }}>
      <DashboardHeader
        theme={theme}
        eyebrow="BASES · CONHECIMENTO CURADO"
        title="Tudo que JUDITE pode citar"
        subtitle="Cada base junta documentos por tema. JUDITE busca primeiro nas bases do projeto atual, depois nas suas pessoais."
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <GhostButton icon="search" label="Buscar" />
            <PrimaryButton icon="plus" label="Nova base" />
          </div>
        }
      />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", flex: 1, overflow: "hidden" }}>
        {/* List */}
        <div style={{ padding: "20px 24px 20px 40px", overflow: "auto", display: "flex", flexDirection: "column", gap: 10 }}>
          {bases.map((b, i) => (
            <KnowledgeRow key={i} base={b} theme={theme} />
          ))}
        </div>
        {/* Detail panel */}
        <div style={{ borderLeft: "1px solid var(--line-soft)", padding: "20px 24px", background: "color-mix(in oklch, var(--bg-ink) 50%, var(--bg))" }}>
          <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>
            base selecionada
          </Mono>
          <div style={{ marginTop: 8, fontSize: 16, fontWeight: 600, color: "var(--text)", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--ember)", transform: "rotate(45deg)", boxShadow: "0 0 8px var(--ember-glow)" }} />
            RAG · documentação pessoal
          </div>
          <div style={{ marginTop: 4, fontSize: 12.5, color: "var(--muted)", lineHeight: 1.5 }}>
            Notas pessoais, runbooks, snippets. Tudo que vale lembrar fora da memória.
          </div>

          <Divider style={{ margin: "18px 0" }} />

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <DetailRow label="documentos" value="124" />
            <DetailRow label="chunks indexados" value="3.4k" />
            <DetailRow label="tokens por consulta" value="máx. 8 · 3 chunks/doc" />
            <DetailRow label="atualizada" value="há 2h" />
            <DetailRow label="vetor" value="text-embedding-3-large" mono />
          </div>

          <Divider style={{ margin: "18px 0" }} />

          <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>
            buscas recentes
          </Mono>
          <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
            {["como configurar tailscale", "pgvector hnsw", "backup notion postgres"].map((q, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--text-soft)" }}>
                <Icon name="search" size={11} stroke="var(--faint)" />
                <span style={{ flex: 1 }}>{q}</span>
                <Mono size={9.5} color="var(--faint)">
                  {7 - i * 2} resultados
                </Mono>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function KnowledgeRow({ base, theme }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr auto auto auto",
        alignItems: "center",
        gap: 16,
        padding: "14px 16px",
        borderRadius: "var(--radius)",
        background: base.active ? "color-mix(in oklch, var(--ember) 5%, var(--bg-card))" : "var(--bg-card)",
        border: base.active ? "1px solid color-mix(in oklch, var(--ember) 22%, transparent)" : "1px solid var(--line-soft)",
      }}
    >
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 8,
          background: `linear-gradient(155deg, ${base.color}, color-mix(in oklch, ${base.color} 30%, var(--bg-ink)))`,
          border: `1px solid color-mix(in oklch, ${base.color} 30%, var(--line))`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--bg-ink)",
        }}
      >
        <Icon name="database" size={15} />
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text)", display: "flex", alignItems: "center", gap: 8 }}>
          {base.name}
          {base.active && <Tag tone="ember"><Pulse color="var(--ember)" size={4} /> em uso</Tag>}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6 }}>
          {base.tags.map((t) => (
            <Mono key={t} size={10} color="var(--muted)" style={{ padding: "2px 7px", borderRadius: 4, background: "var(--bg-chip)" }}>
              {t}
            </Mono>
          ))}
        </div>
      </div>
      <DetailMini label="docs" value={base.docs} theme={theme} />
      <DetailMini label="chunks" value={base.chunks} theme={theme} />
      <Mono size={10} color="var(--faint)">
        há {base.updated}
      </Mono>
    </div>
  );
}

function DetailRow({ label, value, mono }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
      <Mono size={10.5} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.1em" }}>
        {label}
      </Mono>
      <span style={{ fontSize: 12.5, color: "var(--text)", fontFamily: mono ? "var(--font-mono)" : "inherit" }}>{value}</span>
    </div>
  );
}

function DetailMini({ label, value, theme }) {
  return (
    <div style={{ textAlign: "right", minWidth: 50 }}>
      <Mono size={9.5} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>
        {label}
      </Mono>
      <div style={{ fontSize: 15, color: "var(--text)", fontWeight: 400, fontFamily: "var(--font-display)", letterSpacing: "0.005em", marginTop: 2 }}>
        {value}
      </div>
    </div>
  );
}

// Files view
function FilesDashboard({ theme }) {
  const files = [
    { name: "schema-rag-v3.sql", type: "sql", size: "12 KB", project: "Forja pessoal", indexed: true, updated: "2h" },
    { name: "diagrama-rag.png", type: "image", size: "287 KB", project: "Forja pessoal", indexed: false, updated: "2h" },
    { name: "tese-cap-3.md", type: "md", size: "48 KB", project: "Tese mestrado", indexed: true, updated: "5h" },
    { name: "audit-export-mar.csv", type: "csv", size: "1.2 MB", project: "Forja pessoal", indexed: true, updated: "1d" },
    { name: "ferro-system-prompt.txt", type: "txt", size: "4 KB", project: "Agentes", indexed: true, updated: "2d" },
    { name: "contrato-vasques-v2.pdf", type: "pdf", size: "320 KB", project: "Cliente · Vasques", indexed: false, updated: "5d" },
    { name: "blender-scene.fbx", type: "3d", size: "8.4 MB", project: "MCP 3D", indexed: false, updated: "1sem" },
  ];

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, background: "var(--bg)", overflow: "hidden" }}>
      <DashboardHeader
        theme={theme}
        eyebrow="ARQUIVOS · 248 ITENS"
        title="A despensa"
        subtitle="Uploads, imports, anexos de chat e arquivos gerados. Indexados quando útil, lá quando precisar."
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <GhostButton icon="filter" label="Filtrar" />
            <PrimaryButton icon="plus" label="Importar" />
          </div>
        }
      />

      <div style={{ padding: "20px 40px", overflow: "auto", flex: 1 }}>
        <div style={{ background: "var(--bg-card)", border: "1px solid var(--line-soft)", borderRadius: "var(--radius)", overflow: "hidden" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1.5fr 90px 80px 1.2fr 80px 90px", padding: "10px 18px", borderBottom: "1px solid var(--line-soft)", background: "var(--bg-ink)" }}>
            {["nome", "tipo", "tamanho", "projeto", "índice", "modificado"].map((h) => (
              <Mono key={h} size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>
                {h}
              </Mono>
            ))}
          </div>
          {files.map((f, i) => (
            <div key={i} style={{ display: "grid", gridTemplateColumns: "1.5fr 90px 80px 1.2fr 80px 90px", padding: "12px 18px", borderBottom: i === files.length - 1 ? "none" : "1px solid var(--line-soft)", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <FileIcon type={f.type} />
                <span style={{ fontSize: 13, color: "var(--text)" }}>{f.name}</span>
              </div>
              <Mono size={11} color="var(--muted)">{f.type}</Mono>
              <Mono size={11} color="var(--muted)">{f.size}</Mono>
              <span style={{ fontSize: 12, color: "var(--text-soft)" }}>{f.project}</span>
              {f.indexed ? <Tag tone="ok">indexado</Tag> : <Tag tone="neutral">—</Tag>}
              <Mono size={10} color="var(--faint)">há {f.updated}</Mono>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function FileIcon({ type }) {
  const colors = {
    sql: "var(--azure)",
    image: "#5acf8c",
    md: "var(--ember)",
    csv: "var(--amethyst)",
    txt: "var(--muted)",
    pdf: "var(--err)",
    "3d": "var(--amethyst)",
  };
  return (
    <div style={{ width: 26, height: 26, borderRadius: 6, background: "var(--bg-chip)", border: `1px solid color-mix(in oklch, ${colors[type] || "var(--line)"} 30%, transparent)`, display: "flex", alignItems: "center", justifyContent: "center", color: colors[type] || "var(--muted)", flexShrink: 0 }}>
      <Mono size={9} color={colors[type] || "var(--muted)"} style={{ fontWeight: 600 }}>
        {type.toUpperCase().slice(0, 3)}
      </Mono>
    </div>
  );
}

Object.assign(window, { AgentDashboard, KnowledgeDashboard, FilesDashboard, PrimaryButton, GhostButton });
