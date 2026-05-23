// Minor components — command palette, dropdowns, tooltips, toasts, skeleton, empty, streaming

// 1) Command palette (⌘K)
function CommandPalette() {
  const items = [
    { group: "Ações", entries: [
      { icon: "plus", label: "Nova conversa", kbd: "⌘N" },
      { icon: "sparkles", label: "Nova com JUDITE", kbd: "⌘⇧N" },
      { icon: "folder", label: "Novo projeto", kbd: "⌘P" },
      { icon: "database", label: "Nova base de conhecimento", kbd: "⌘B" },
    ]},
    { group: "Ir para", entries: [
      { icon: "users", label: "Agentes" },
      { icon: "file-text", label: "Arquivos" },
      { icon: "shield", label: "Auditoria · maio" },
    ]},
    { group: "Conversas recentes", entries: [
      { icon: "message-square", label: "Pipeline RAG no Postgres", hint: "agora", active: true },
      { icon: "message-square", label: "Configurar Tailscale", hint: "ontem" },
      { icon: "message-square", label: "Migrar prompts pra Postgres", hint: "3d" },
    ]},
  ];
  return (
    <div style={{ width: 560, borderRadius: "var(--radius-lg)", background: "var(--bg-elev)", border: "1px solid var(--line)", boxShadow: "0 24px 80px -24px var(--ember-glow), 0 1px 0 0 color-mix(in srgb, var(--ember) 12%, transparent)", overflow: "hidden" }}>
      <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--line-soft)", display: "flex", alignItems: "center", gap: 12 }}>
        <Icon name="search" size={15} stroke="var(--ember)" />
        <div style={{ flex: 1, fontSize: 14, color: "var(--text)" }}>
          rag postgres
          <span style={{ display: "inline-block", width: 1.5, height: 16, background: "var(--ember)", marginLeft: 4, verticalAlign: "text-bottom", animation: "tfBlink 1s infinite" }} />
        </div>
        <Mono size={10} color="var(--faint)">
          <KBD>esc</KBD> fechar
        </Mono>
      </div>
      <div style={{ padding: "8px 8px 12px", maxHeight: 380, overflow: "auto" }}>
        {items.map((g) => (
          <div key={g.group} style={{ marginTop: 6 }}>
            <div style={{ padding: "8px 12px 4px" }}>
              <Mono size={9.5} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>
                {g.group}
              </Mono>
            </div>
            {g.entries.map((it, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "9px 12px",
                  borderRadius: 8,
                  background: it.active ? "color-mix(in srgb, var(--ember) 10%, transparent)" : "transparent",
                  color: it.active ? "var(--text)" : "var(--text-soft)",
                }}
              >
                <Icon name={it.icon} size={13} stroke={it.active ? "var(--ember)" : "var(--muted)"} />
                <span style={{ flex: 1, fontSize: 13 }}>{it.label}</span>
                {it.hint && <Mono size={10} color="var(--faint)">{it.hint}</Mono>}
                {it.kbd && <KBD>{it.kbd}</KBD>}
                {it.active && <Icon name="chevron-right" size={12} stroke="var(--ember)" />}
              </div>
            ))}
          </div>
        ))}
      </div>
      <div style={{ padding: "10px 18px", borderTop: "1px solid var(--line-soft)", display: "flex", alignItems: "center", gap: 16, background: "color-mix(in srgb, var(--bg-ink) 50%, var(--bg-elev))" }}>
        <Mono size={10} color="var(--muted)" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <KBD>↑↓</KBD> navegar
        </Mono>
        <Mono size={10} color="var(--muted)" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <KBD>↵</KBD> abrir
        </Mono>
        <span style={{ flex: 1 }} />
        <Mono size={10} color="var(--faint)">12 resultados</Mono>
      </div>
    </div>
  );
}

// 2) Dropdown — execution menu (modo)
function ExecutionMenu() {
  const items = [
    { label: "Raciocínio padrão", on: true, hint: "rápido · 1-3s" },
    { label: "Raciocínio longo", hint: "+10-30s · etapas detalhadas" },
    { label: "Resumo oficial", hint: "OpenAI · só texto" },
    { label: "Pesquisa profunda", hint: "2-8 min · até 30 chamadas" },
    { label: "Geração de imagem", hint: "dall-e 3 · 1024×1024" },
    { label: "Multi-agente", hint: "JUDITE + 2 apoios", purple: true },
    { label: "MCP 3D", hint: "Blender · Fusion", purple: true },
  ];
  return (
    <div style={{ width: 320, padding: 8, borderRadius: "var(--radius)", background: "var(--bg-elev)", border: "1px solid var(--line)", boxShadow: "var(--shadow-soft), 0 24px 60px -24px rgba(0,0,0,0.6)" }}>
      <div style={{ padding: "6px 8px 8px", display: "flex", alignItems: "center", gap: 8 }}>
        <Icon name="activity" size={12} stroke="var(--ember)" />
        <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>
          modo de execução
        </Mono>
      </div>
      {items.map((it, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "8px 10px",
            borderRadius: 6,
            background: it.on ? "color-mix(in srgb, var(--ember) 8%, transparent)" : "transparent",
          }}
        >
          <span
            style={{
              width: 14,
              height: 14,
              borderRadius: 4,
              border: `1.5px solid ${it.on ? (it.purple ? "var(--amethyst)" : "var(--ember)") : "var(--line)"}`,
              background: it.on ? (it.purple ? "var(--amethyst)" : "var(--ember)") : "transparent",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {it.on && <Icon name="check" size={9} stroke={it.purple ? "#fff" : "var(--ember-ink)"} strokeWidth={3} />}
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12.5, color: "var(--text)" }}>{it.label}</div>
            <Mono size={9.5} color="var(--faint)" style={{ marginTop: 1, display: "block" }}>
              {it.hint}
            </Mono>
          </div>
        </div>
      ))}
      <div style={{ marginTop: 4, padding: "8px 10px", borderTop: "1px solid var(--line-soft)" }}>
        <div style={{ fontSize: 11.5, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6 }}>
          <Icon name="paperclip" size={11} stroke="var(--muted)" />
          Anexar arquivo
          <span style={{ flex: 1 }} />
          <KBD>⌘U</KBD>
        </div>
      </div>
    </div>
  );
}

// 3) Mention popover — @pasta
function MentionPopover() {
  const items = [
    { label: "Forja_pessoal / plano-financeiro", count: 4 },
    { label: "Forja_pessoal / estudos / sistemas-distribuidos", count: 12, active: true },
    { label: "Tese_de_mestrado / cap-3", count: 8 },
    { label: "Cliente_Vasques / contratos", count: 3 },
  ];
  return (
    <div style={{ width: 380, padding: 6, borderRadius: 10, background: "var(--bg-elev)", border: "1px solid var(--line)", boxShadow: "var(--shadow-soft)" }}>
      <div style={{ padding: "6px 10px 8px" }}>
        <Mono size={9.5} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>
          @ pastas de contexto
        </Mono>
      </div>
      {items.map((it) => (
        <div
          key={it.label}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 10px",
            borderRadius: 6,
            background: it.active ? "color-mix(in srgb, var(--ember) 10%, transparent)" : "transparent",
          }}
        >
          <Icon name="hash" size={11} stroke={it.active ? "var(--ember)" : "var(--faint)"} />
          <span style={{ flex: 1, fontFamily: "var(--font-mono)", fontSize: 11.5, color: it.active ? "var(--text)" : "var(--text-soft)" }}>{it.label}</span>
          <Mono size={9.5} color="var(--faint)">{it.count}</Mono>
        </div>
      ))}
    </div>
  );
}

// 4) Tooltip
function Tooltip({ label, hint }) {
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 12 }}>
      <div style={{ width: 36, height: 36, borderRadius: 10, background: "var(--bg-card)", border: "1px solid var(--line-soft)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted)" }}>
        <Icon name="paperclip" size={15} />
      </div>
      <div style={{ position: "relative", padding: "8px 12px", borderRadius: 8, background: "var(--bg-ink)", border: "1px solid var(--line)", boxShadow: "0 8px 24px -16px rgba(0,0,0,0.8)" }}>
        <span style={{ position: "absolute", left: -5, top: "50%", transform: "translateY(-50%) rotate(45deg)", width: 8, height: 8, background: "var(--bg-ink)", borderLeft: "1px solid var(--line)", borderBottom: "1px solid var(--line)" }} />
        <div style={{ fontSize: 12, color: "var(--text)", lineHeight: 1.4 }}>{label}</div>
        {hint && (
          <Mono size={9.5} color="var(--faint)" style={{ marginTop: 4, display: "block" }}>
            {hint}
          </Mono>
        )}
      </div>
    </div>
  );
}

// 5) Toasts
function Toasts() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, width: 360 }}>
      <Toast tone="ok" icon="check" title="Base salva" body='"RAG · documentação pessoal" atualizada · 124 docs.' />
      <Toast tone="ember" icon="sparkles" title="JUDITE precisa decidir" body="2 caminhos para o pipeline. Toque para revisar." action="Revisar" />
      <Toast tone="amethyst" icon="boxes" title="Blender conectado" body="MCP 3D ativo · v4.2 · porta 9876." />
      <Toast tone="err" icon="shield" title="Custo perto do teto" body="80% do orçamento de maio — restam R$ 39,72." />
    </div>
  );
}

function Toast({ tone = "ok", icon, title, body, action }) {
  const palette = {
    ok: { color: "var(--ok)", glow: "rgba(90,207,140,0.25)" },
    ember: { color: "var(--ember)", glow: "var(--ember-glow)" },
    amethyst: { color: "var(--amethyst)", glow: "var(--amethyst-glow)" },
    azure: { color: "var(--azure)", glow: "var(--azure-glow)" },
    err: { color: "var(--err)", glow: "rgba(255,90,74,0.25)" },
  }[tone];
  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        gap: 12,
        padding: "12px 14px",
        borderRadius: 12,
        background: "var(--bg-elev)",
        border: "1px solid var(--line)",
        boxShadow: `0 16px 36px -20px ${palette.glow}, 0 1px 0 0 color-mix(in srgb, ${palette.color} 14%, transparent)`,
        overflow: "hidden",
      }}
    >
      <span style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: palette.color, boxShadow: `0 0 12px ${palette.glow}` }} />
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: 8,
          background: `color-mix(in srgb, ${palette.color} 14%, transparent)`,
          color: palette.color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <Icon name={icon} size={14} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, color: "var(--text)", fontWeight: 500 }}>{title}</div>
        <div style={{ marginTop: 3, fontSize: 12, color: "var(--muted)", lineHeight: 1.5 }}>{body}</div>
      </div>
      {action && (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: palette.color, alignSelf: "center", whiteSpace: "nowrap", letterSpacing: "0.04em" }}>{action} →</span>
      )}
    </div>
  );
}

// 6) Skeleton loaders
function Skeletons() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.14em", display: "block", marginBottom: 10 }}>
          carregando conversas
        </Mono>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[0.9, 0.7, 0.85, 0.6].map((w, i) => (
            <div key={i} style={{ height: 14, borderRadius: 4, width: `${w * 100}%`, background: "linear-gradient(90deg, var(--bg-card), var(--bg-hover), var(--bg-card))", backgroundSize: "200% 100%", animation: "tfShimmer 1.4s infinite" }} />
          ))}
        </div>
      </div>
      <div>
        <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.14em", display: "block", marginBottom: 10 }}>
          JUDITE está respondendo
        </Mono>
        <div style={{ display: "flex", gap: 12, padding: 14, background: "var(--bg-card)", borderRadius: "var(--radius)", border: "1px solid var(--line-soft)" }}>
          <Avatar kind="judite" size={28} />
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ height: 12, borderRadius: 4, width: "30%", background: "var(--bg-hover)" }} />
            <div style={{ display: "flex", gap: 4, marginTop: 4 }}>
              <Dot delay={0} />
              <Dot delay={0.2} />
              <Dot delay={0.4} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Dot({ delay = 0 }) {
  return (
    <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--ember)", animation: "tfDot 1s infinite ease-in-out", animationDelay: `${delay}s`, display: "inline-block" }} />
  );
}

// 7) Empty states (small)
function EmptyState({ icon, title, hint, action }) {
  return (
    <div style={{ padding: "32px 28px", borderRadius: "var(--radius)", border: "1px dashed var(--line)", background: "color-mix(in srgb, var(--bg-card) 50%, transparent)", display: "flex", flexDirection: "column", alignItems: "center", gap: 12, textAlign: "center" }}>
      <div style={{ width: 44, height: 44, borderRadius: 12, background: "color-mix(in srgb, var(--ember) 8%, var(--bg-ink))", border: "1px solid color-mix(in srgb, var(--ember) 22%, transparent)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--ember)" }}>
        <Icon name={icon} size={18} />
      </div>
      <div>
        <div style={{ fontFamily: "var(--font-display)", fontSize: 16, color: "var(--text)", letterSpacing: "0.01em", textTransform: "uppercase" }}>{title}</div>
        <div style={{ marginTop: 6, fontSize: 12.5, color: "var(--muted)", maxWidth: 240, lineHeight: 1.55, margin: "6px auto 0" }}>{hint}</div>
      </div>
      {action}
    </div>
  );
}

function EmptyStates() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
      <EmptyState icon="folder" title="Nenhum projeto" hint="Crie um projeto para organizar conversas, pastas e bases por tema." action={<GhostButton icon="plus" label="Novo projeto" />} />
      <EmptyState icon="database" title="Sem bases" hint="Bases agrupam documentos por escopo. JUDITE consulta antes de responder." action={<GhostButton icon="plus" label="Nova base" />} />
      <EmptyState icon="shield" title="Auditoria limpa" hint="Nada para revisar em maio. Custos dentro do limite e sem alertas." />
    </div>
  );
}

// 8) Streaming reasoning track (live state)
function StreamingTrack() {
  const steps = [
    { label: "Buscando contexto", status: "done", detail: "12 chunks de 2 bases" },
    { label: "Cruzando referências", status: "done", detail: "schema-rag-v3.sql · pgvector-runbook.md" },
    { label: "Compondo resposta", status: "active", detail: "1.2s · ~280 tok" },
    { label: "Anexando código", status: "pending" },
    { label: "Citando fontes", status: "pending" },
  ];
  return (
    <div style={{ width: 480, padding: "16px 18px", background: "var(--bg-card)", border: "1px solid var(--line-soft)", borderRadius: "var(--radius)", boxShadow: "var(--shadow-soft)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
        <Icon name="brain" size={13} stroke="var(--ember)" />
        <Mono size={10.5} color="var(--text-soft)" style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>
          trilha de raciocínio · ao vivo
        </Mono>
        <span style={{ flex: 1 }} />
        <div style={{ display: "flex", gap: 3 }}>
          <Dot delay={0} />
          <Dot delay={0.2} />
          <Dot delay={0.4} />
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12, position: "relative" }}>
        <span style={{ position: "absolute", left: 5, top: 6, bottom: 6, width: 1, background: "var(--line-soft)" }} />
        {steps.map((s, i) => (
          <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 12, position: "relative" }}>
            <span
              style={{
                width: 11,
                height: 11,
                borderRadius: 999,
                background: s.status === "done" ? "var(--ember)" : s.status === "active" ? "var(--ember)" : "var(--bg-ink)",
                border: s.status === "pending" ? "1.5px solid var(--line)" : "none",
                marginTop: 3,
                boxShadow: s.status === "active" ? "0 0 0 4px var(--ember-glow)" : "none",
                flexShrink: 0,
                position: "relative",
                zIndex: 1,
              }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, color: s.status === "pending" ? "var(--faint)" : "var(--text)", fontWeight: s.status === "active" ? 500 : 400 }}>{s.label}</div>
              {s.detail && (
                <Mono size={10} color={s.status === "active" ? "var(--ember)" : "var(--faint)"} style={{ marginTop: 2, display: "block" }}>
                  {s.detail}
                </Mono>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Scene
function ComponentsScene({ theme }) {
  return (
    <div style={{ ...themeVars(theme), width: "100%", height: "100%", background: "var(--bg-ink)", padding: "40px", overflow: "auto", fontFamily: "var(--font-text)", position: "relative" }}>
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(circle at 1px 1px, var(--line-soft) 1px, transparent 0)", backgroundSize: "32px 32px", opacity: 0.35, pointerEvents: "none" }} />
      <div style={{ position: "relative", display: "flex", flexDirection: "column", gap: 32 }}>
        <div>
          <Mono size={11} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.2em" }}>
            sistema · componentes menores
          </Mono>
          <h2 style={{ margin: "10px 0 0", fontFamily: "var(--font-display)", fontSize: 32, fontWeight: 400, letterSpacing: "0.01em", textTransform: "uppercase", color: "var(--text)" }}>
            Detalhes da forja
          </h2>
        </div>

        <Group label="Command palette · ⌘K">
          <CommandPalette />
        </Group>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32, alignItems: "start" }}>
          <Group label="Dropdown · modo de execução">
            <ExecutionMenu />
          </Group>
          <Group label="Mention popover · @pasta">
            <MentionPopover />
            <div style={{ marginTop: 18 }}>
              <Group label="Tooltip">
                <Tooltip label="Anexar arquivo ao chat" hint="ou arraste para a janela" />
              </Group>
            </div>
          </Group>
        </div>

        <Group label="Streaming · trilha de raciocínio">
          <StreamingTrack />
        </Group>

        <Group label="Toasts · notificações">
          <Toasts />
        </Group>

        <Group label="Estados vazios">
          <EmptyStates />
        </Group>

        <Group label="Skeletons · carregamento">
          <Skeletons />
        </Group>
      </div>
    </div>
  );
}

function Group({ label, children }) {
  return (
    <div>
      <div style={{ marginBottom: 14, display: "flex", alignItems: "center", gap: 10 }}>
        <Mono size={10.5} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.16em" }}>
          {label}
        </Mono>
        <span style={{ flex: 1, height: 1, background: "var(--line-soft)" }} />
      </div>
      {children}
    </div>
  );
}

Object.assign(window, {
  ComponentsScene, CommandPalette, ExecutionMenu, MentionPopover, Tooltip, Toasts, Toast, Skeletons, EmptyState, EmptyStates, StreamingTrack,
});
