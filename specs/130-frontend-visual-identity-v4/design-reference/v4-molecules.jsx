// v4 — New & gap-filling Molecules
// Tier: P1 (SearchField, ProviderStatusRow, AuditEventRow, PromptCard, IndexingStatusBadge)
//       NEW (FilterPillRow, PlanStepRow, AdapterStatusRow, TraceEventDetails, WarningBanner)
//       P2 (MetricTile decision)

// ─── Preview primitives ──────────────────────────────────────────────────────

function PV_SearchField({ width = 280, placeholder = "Buscar contexto…", buttonLabel = "Buscar" }) {
  return (
    <div style={{ width, display: "flex", gap: 8 }}>
      <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8, padding: "0 10px 0 12px", height: 36, background: "var(--bg-ink)", border: "1px solid var(--line-soft)", borderRadius: 8 }}>
        <Icon name="search" size={13} stroke="var(--muted)" />
        <span style={{ fontSize: 13, color: "var(--muted)" }}>{placeholder}</span>
      </div>
      <button style={{ height: 36, padding: "0 14px", background: "color-mix(in srgb, var(--ember) 14%, var(--bg-card))", border: "1px solid color-mix(in srgb, var(--ember) 40%, transparent)", borderRadius: 8, color: "var(--ember)", fontFamily: "var(--font-mono)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.12em", fontWeight: 600, cursor: "pointer" }}>
        {buttonLabel}
      </button>
    </div>
  );
}

function PV_ProviderStatusRow({ provider, state }) {
  const stateMap = {
    env:      { label: "env",      color: "var(--ok)" },
    vault:    { label: "vault",    color: "var(--azure)" },
    pendente: { label: "pendente", color: "var(--ember)" },
    editing:  { label: "editando", color: "var(--amethyst)" },
  };
  const s = stateMap[state];
  const isEditing = state === "editing";
  const isPending = state === "pendente";
  return (
    <div style={{ width: 480, padding: "12px 14px", background: "var(--bg-card)", border: "1px solid var(--line-soft)", borderRadius: 8, display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ width: 28, height: 28, borderRadius: 6, background: "var(--bg-ink)", border: "1px solid var(--line-soft)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-mono)", fontSize: 9.5, fontWeight: 600, color: "var(--text)", textTransform: "uppercase" }}>
        {provider.slice(0, 2)}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, color: "var(--text)", textTransform: "capitalize" }}>{provider}</div>
        <Mono size={10} color="var(--faint)">api.{provider}.com</Mono>
      </div>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "3px 9px", borderRadius: 999, background: `color-mix(in srgb, ${s.color} 12%, transparent)`, color: s.color, border: `1px solid color-mix(in srgb, ${s.color} 30%, transparent)`, fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.12em", fontWeight: 600 }}>
        <span style={{ width: 5, height: 5, borderRadius: 999, background: s.color }} />
        {s.label}
      </span>
      {isEditing && (
        <div style={{ width: 140, height: 28, background: "var(--bg-ink)", border: "1px solid var(--line-soft)", borderRadius: 6, padding: "0 8px", display: "flex", alignItems: "center", fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-soft)" }}>
          sk-•••••••3a9f
        </div>
      )}
      {(isEditing || isPending) && (
        <button style={{ height: 28, padding: "0 10px", background: "color-mix(in srgb, var(--ember) 14%, var(--bg-card))", border: "1px solid color-mix(in srgb, var(--ember) 40%, transparent)", borderRadius: 6, color: "var(--ember)", fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 600 }}>
          Salvar
        </button>
      )}
      {!isEditing && !isPending && (
        <button style={{ height: 28, padding: "0 10px", background: "transparent", border: "1px solid var(--line-soft)", borderRadius: 6, color: "var(--muted)", fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em" }}>
          Editar
        </button>
      )}
    </div>
  );
}

function PV_AuditEventRow() {
  return (
    <div style={{ width: 520, padding: "12px 14px", background: "var(--bg-card)", border: "1px solid var(--line-soft)", borderRadius: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <Mono size={11} color="var(--ember)" style={{ fontWeight: 600 }}>chat.message.completed</Mono>
        <span style={{ padding: "2px 8px", borderRadius: 4, background: "var(--bg-ink)", border: "1px solid var(--line-soft)", fontFamily: "var(--font-mono)", fontSize: 9.5, color: "var(--text-soft)" }}>gpt-4o</span>
        <span style={{ flex: 1 }} />
        <Mono size={9.5} color="var(--faint)">12:42:18</Mono>
      </div>
      <Mono size={10.5} color="var(--muted)">1,287 in / 480 out · R$ 0,0186 · 1.2s</Mono>
    </div>
  );
}

function PV_PromptCard({ favorite = false }) {
  return (
    <div style={{ width: 240, padding: 12, background: "var(--bg-card)", border: `1px solid ${favorite ? "color-mix(in srgb, var(--ember) 30%, transparent)" : "var(--line-soft)"}`, borderRadius: 8, cursor: "pointer" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 13, color: "var(--text)", fontWeight: 500 }}>Resumo de reunião</span>
        {favorite && (
          <span style={{ marginLeft: "auto", padding: "2px 7px", borderRadius: 999, background: "color-mix(in srgb, var(--ember) 14%, transparent)", color: "var(--ember)", fontFamily: "var(--font-mono)", fontSize: 9, textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 600 }}>★</span>
        )}
      </div>
      <p style={{ margin: 0, fontSize: 11.5, color: "var(--muted)", lineHeight: 1.5, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
        Resuma a reunião em 3 bullets: decisões, action items com owners e prazos, e bloqueios.
      </p>
    </div>
  );
}

function PV_IndexingStatusBadge({ count }) {
  const empty = count === 0;
  const color = empty ? "var(--ok)" : "var(--ember)";
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "5px 10px", borderRadius: 6, background: "var(--bg-card)", border: `1px solid color-mix(in srgb, ${color} 30%, var(--line-soft))` }}>
      {!empty && (
        <span style={{ position: "relative", width: 7, height: 7 }}>
          <span style={{ position: "absolute", inset: 0, borderRadius: 999, background: color }} />
          <span style={{ position: "absolute", inset: 0, borderRadius: 999, background: color, animation: "tfPulse 1.6s ease-out infinite" }} />
        </span>
      )}
      {empty && <span style={{ width: 7, height: 7, borderRadius: 999, background: color }} />}
      <Mono size={10.5} color="var(--text-soft)" style={{ fontWeight: 500 }}>
        {empty ? "tudo indexado" : `${count} arquivos na fila`}
      </Mono>
    </div>
  );
}

function PV_FilterPillRow() {
  const items = [
    { label: "debug", active: false },
    { label: "info",  active: true },
    { label: "warn",  active: true },
    { label: "error", active: true },
  ];
  return (
    <div style={{ display: "flex", gap: 6 }}>
      {items.map((it) => (
        <span key={it.label} style={{
          padding: "3px 10px", borderRadius: 999,
          background: it.active ? "var(--bg-card)" : "transparent",
          border: `1px solid ${it.active ? "var(--line-soft)" : "color-mix(in srgb, var(--line-soft) 30%, transparent)"}`,
          color: it.active ? "var(--text)" : "color-mix(in srgb, var(--muted) 60%, transparent)",
          fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.12em", cursor: "pointer",
        }}>{it.label}</span>
      ))}
    </div>
  );
}

function PV_PlanStepRow() {
  return (
    <div style={{ width: 380, padding: "8px 10px", background: "var(--bg-ink)", border: "1px solid var(--line-soft)", borderRadius: 6 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span style={{ fontSize: 12, color: "var(--text)", fontWeight: 500 }}>
          <span style={{ color: "var(--faint)" }}>02.</span> Criar cilindro base
        </span>
        <PV_RiskPill level="medium" />
      </div>
      <Mono size={10} color="var(--muted)" style={{ marginTop: 4, display: "block" }}>
        blender.mesh.add_cylinder · aprovação inline
      </Mono>
    </div>
  );
}

function PV_AdapterStatusRow() {
  return (
    <div style={{ width: 380, padding: "10px 12px", background: "var(--bg-card)", border: "1px solid var(--line-soft)", borderRadius: 8 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span style={{ fontSize: 13, color: "var(--text)", fontWeight: 500 }}>Blender 4.2</span>
        <span style={{ padding: "2px 9px", borderRadius: 999, background: "color-mix(in srgb, var(--ok) 14%, transparent)", color: "var(--ok)", border: "1px solid color-mix(in srgb, var(--ok) 30%, transparent)", fontFamily: "var(--font-mono)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.12em", fontWeight: 600 }}>conectado</span>
      </div>
      <Mono size={10.5} color="var(--muted)" style={{ marginTop: 4, display: "block" }}>websocket · localhost:8932 · last ping 8s</Mono>
    </div>
  );
}

function PV_TraceEventDetails({ open = true }) {
  return (
    <div style={{ width: 460, padding: "8px 10px", background: "var(--bg-card)", border: "1px solid var(--line-soft)", borderRadius: 6, fontSize: 11.5 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ padding: "2px 7px", borderRadius: 4, background: "var(--bg-ink)", fontFamily: "var(--font-mono)", fontSize: 9, textTransform: "uppercase", color: "var(--muted)" }}>mcp</span>
          <span style={{ color: "var(--ember)", fontWeight: 500 }}>tool.call.start</span>
          <Mono size={10} color="var(--muted)">· 842ms</Mono>
        </div>
        <Mono size={9.5} color="var(--faint)">12:42:18.394</Mono>
      </div>
      {open && (
        <pre style={{ margin: "8px 0 0", padding: 8, background: "var(--bg-ink)", borderRadius: 4, fontFamily: "var(--font-mono)", fontSize: 9.5, color: "var(--muted)", overflow: "hidden", lineHeight: 1.5 }}>{`{ "tool": "blender.mesh.add_cylinder",
  "args": { "radius": 1.5, "height": 3 } }`}</pre>
      )}
    </div>
  );
}

function PV_WarningBanner({ tone = "ember", title, body }) {
  const color = tone === "err" ? "var(--err)" : "var(--ember)";
  return (
    <div style={{ width: 480, padding: "10px 12px", background: `color-mix(in srgb, ${color} 10%, var(--bg-card))`, border: `1px solid color-mix(in srgb, ${color} 45%, transparent)`, borderRadius: 8, display: "flex", alignItems: "flex-start", gap: 10 }}>
      <Icon name="shield" size={14} stroke={color} style={{ marginTop: 1, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, color: color, fontWeight: 600 }}>{title}</div>
        {body && <div style={{ marginTop: 2, fontSize: 12, color: "var(--text-soft)", lineHeight: 1.5 }}>{body}</div>}
      </div>
    </div>
  );
}

function PV_MetricTile() {
  return (
    <div style={{ display: "flex", gap: 10 }}>
      <div style={{ width: 110, padding: "8px 10px", background: "var(--bg-card)", border: "1px solid var(--line-soft)", borderRadius: 6 }}>
        <Mono size={10} color="var(--muted)" style={{ textTransform: "uppercase", letterSpacing: "0.1em" }}>chats</Mono>
        <div style={{ marginTop: 2, fontSize: 18, color: "var(--text)", fontFamily: "var(--font-display)", letterSpacing: "0.005em" }}>247</div>
      </div>
      <div style={{ width: 110, padding: "8px 10px", background: "var(--bg-card)", border: "1px solid var(--line-soft)", borderRadius: 6 }}>
        <Mono size={10} color="var(--muted)" style={{ textTransform: "uppercase", letterSpacing: "0.1em" }}>tokens</Mono>
        <div style={{ marginTop: 2, fontSize: 18, color: "var(--text)", fontFamily: "var(--font-display)", letterSpacing: "0.005em" }}>1.2M</div>
      </div>
    </div>
  );
}

// ─── The molecules section ───────────────────────────────────────────────────

function V4_MoleculesSection() {
  return (
    <DocSection
      id="v4-molecules"
      eyebrow="04 · Moléculas"
      title="Moléculas"
      intro="Composições recorrentes. Cada molécula combina átomos em uma forma estável — props fixas, comportamentos definidos."
    >
      <V4Spec
        id="mol-searchfield"
        tier="p1"
        name="SearchField"
        level="molecule"
        summary="Input com prefixo Icon `search` + botão de submit ao lado. Submit on Enter, loading state quando busca está em vôo. Substitui as 3 implementações avulsas no codebase."
        summaryEn="Input with prefixed search icon + adjacent submit button. Submits on Enter, shows loading state during query."
        props={[
          { name: "value", type: "string", desc: "Termo atual" },
          { name: "placeholder", type: "string", desc: "Hint vazio" },
          { name: "buttonLabel", type: "string", desc: "Texto do botão", default: "\"Buscar\"" },
          { name: "loading", type: "boolean", desc: "Spinner no botão" },
          { name: "onSubmit", type: "(q: string) => void", desc: "Callback Enter ou click" },
        ]}
        when={[
          "Painel de contexto · buscar arquivo/documento",
          "KnowledgeDashboard · buscar documento da base",
          "Sidebar / projeto · filtrar conversas",
          "Para search inline sem botão, use Input com prefix Icon",
        ]}
        refs={[
          "web/src/App.tsx · 'Buscar contexto' (~linha 3132)",
          "web/src/features/dashboard/dashboard-sections.tsx · busca de documentos",
          "web/src/features/chat/context-knowledge-bases-modal.tsx · busca de bases",
        ]}
        a11y={[
          "role=\"search\" no container",
          "Input com aria-label se sem label visível",
          "Botão com aria-busy quando loading",
        ]}
        code={`<SearchField
  value={query}
  placeholder="Buscar contexto..."
  loading={pending}
  onSubmit={onSearch}
/>`}
      >
        <PV_SearchField />
      </V4Spec>

      <V4Spec
        id="mol-providerstatusrow"
        tier="p1"
        name="ProviderStatusRow"
        level="molecule"
        summary="Linha de provider com 4 estados: env (ok), vault (azure), pendente (ember), editando (amethyst). Cada estado libera ações diferentes (Editar / Salvar / Remover)."
        summaryEn="Provider row with 4 states: env / vault / pendente / editando. Each state exposes different actions."
        props={[
          { name: "provider", type: "ProviderName", desc: "openai · anthropic · google · ..." },
          { name: "state", type: "'env' | 'vault' | 'pendente' | 'editing'", desc: "Estado atual" },
          { name: "secretMasked", type: "string", desc: "Mostrado em editing (sk-•••3a9f)" },
          { name: "onEdit / onSave / onClear", type: "() => void", desc: "Callbacks" },
        ]}
        when={[
          "Painel `config` (lista de chaves de provider)",
          "Onboarding · setar primeiro provider",
          "Settings → API keys",
        ]}
        refs={[
          "web/src/App.tsx · painel `config` (~linhas 3215-3260)",
          "web/src/lib/api.ts · saveProviderKey / clearProviderKey",
        ]}
        a11y={[
          "Input password tem aria-label=\"API key — {provider}\"",
          "Botões em ordem visual = ordem de tab",
          "Estado anunciado via aria-live=\"polite\" quando muda",
        ]}
        code={`<ProviderStatusRow
  provider="openai"
  state="vault"
  secretMasked="sk-•••3a9f"
  onEdit={() => setEditing('openai')}
/>`}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <PV_ProviderStatusRow provider="openai" state="vault" />
          <PV_ProviderStatusRow provider="anthropic" state="editing" />
          <PV_ProviderStatusRow provider="google" state="pendente" />
        </div>
      </V4Spec>

      <V4Spec
        id="mol-auditeventrow"
        tier="p1"
        name="AuditEventRow"
        level="molecule"
        summary="Linha de evento de auditoria. Header: event_type (mono ember) + Tag modelo + timestamp. Footer: tokens in/out + custo + duração (tudo mono)."
        summaryEn="Audit event row. Header: event_type + model tag + timestamp. Footer: tokens in/out + cost + duration."
        props={[
          { name: "event", type: "AuditEvent", desc: "Vem do backend (api.ts · AuditEvent)" },
          { name: "expanded", type: "boolean", desc: "Mostra payload raw" },
        ]}
        when={[
          "Painel `auditoria` (sidebar tab)",
          "Cost Governor · drill-down",
          "NUNCA usar em listagem geral de mensagens — é só para audit",
        ]}
        refs={[
          "web/src/App.tsx · painel `auditoria` (~linhas 3191-3204)",
          "web/src/types/api.ts · AuditEvent",
        ]}
        a11y={[
          "<article> wrapping, aria-label=\"{event_type} em {timestamp}\"",
          "Toggle expanded via Enter no row",
          "Payload JSON em <pre> com role=\"region\"",
        ]}
        code={`<AuditEventRow event={event} />
<AuditEventRow event={event} expanded />`}
      >
        <PV_AuditEventRow />
      </V4Spec>

      <V4Spec
        id="mol-promptcard"
        tier="p1"
        name="PromptCard"
        level="molecule"
        summary="Card de prompt na Biblioteca. Distingue-se do PromptChip (sugestão pill clicável): mostra título + tag favorito + 3 linhas de preview. Click insere no draft do composer."
        summaryEn="Prompt card in the Library. Distinct from PromptChip (suggestion pill): shows title + favorite tag + 3-line preview. Click inserts into composer draft."
        props={[
          { name: "prompt", type: "Prompt", desc: "{ id, title, template, favorite }" },
          { name: "onUse", type: "(p: Prompt) => void", desc: "Inserir no composer" },
        ]}
        when={[
          "Painel `prompts` (lista da biblioteca)",
          "Dashboard de prompts (edição)",
          "Para sugestões inline no chat vazio, use PromptChip",
        ]}
        refs={[
          "web/src/App.tsx · painel `prompts` (~linhas 3208-3225)",
          "web/src/types/api.ts · Prompt",
        ]}
        a11y={[
          "Inteiro é <button> · cursor-pointer · hover ember border",
          "Favorite indicator tem aria-label=\"prompt favorito\"",
          "Title clamp-1 · template line-clamp-3",
        ]}
        code={`<PromptCard prompt={p} onUse={(p) => insertDraft(p.template)} />`}
      >
        <div style={{ display: "flex", gap: 10 }}>
          <PV_PromptCard favorite />
          <PV_PromptCard />
        </div>
      </V4Spec>

      <V4Spec
        id="mol-indexingstatus"
        tier="p1"
        name="IndexingStatusBadge"
        level="molecule"
        summary="Pill compacto com Pulse + contagem da fila de indexação. Vazio: 'tudo indexado' (ok, sem pulse). Com fila: '{n} arquivos na fila' (ember, pulse ativo)."
        summaryEn="Compact pill: Pulse + indexing queue count. Empty = 'tudo indexado' (ok, no pulse). With backlog = ember pulse."
        props={[
          { name: "count", type: "number", desc: "backlog_files do PlatformFileIndexingStatus" },
        ]}
        when={[
          "SidebarFooter (à direita do avatar)",
          "Header do FilesDashboard",
          "Header da KnowledgeDashboard · ao lado do botão Indexar",
        ]}
        refs={[
          "web/src/App.tsx · fileIndexingStatus polling",
          "web/src/types/api.ts · PlatformFileIndexingStatus",
        ]}
        a11y={[
          "aria-live=\"polite\" no container → screen reader anuncia mudanças",
          "Pulse é decorativo · aria-hidden",
          "Texto carrega a info (não confia só na cor)",
        ]}
        code={`<IndexingStatusBadge count={fileIndexingStatus.backlog_files} />`}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-start" }}>
          <PV_IndexingStatusBadge count={3} />
          <PV_IndexingStatusBadge count={0} />
        </div>
      </V4Spec>

      <V4Spec
        id="mol-filterpillrow"
        tier="new"
        name="FilterPillRow"
        level="molecule"
        summary="Linha de pills toggleable. Cada pill liga/desliga um filtro independente (não exclusivos). Ativo: bg-card + border-line-soft. Inativo: border tracejada + texto muted."
        summaryEn="Row of toggleable pills. Independent (non-exclusive) filters. Active: bg-card + border. Inactive: dim + dashed-ish border."
        props={[
          { name: "options", type: "Option[]", desc: "{ value, label }" },
          { name: "selected", type: "Set<string>", desc: "Estado atual" },
          { name: "onChange", type: "(s: Set) => void", desc: "Callback" },
        ]}
        when={[
          "Filtro de níveis no ModelingDiagnosticsModal (debug/info/warn/error)",
          "Filtro de tipos no FilesDashboard (md/sql/pdf/image)",
          "Para filtro exclusivo (1-of-N), usar SegmentedControl em vez",
        ]}
        refs={[
          "web/src/features/modeling-3d/components/ModelingDiagnosticsModal.tsx · traceLevelFilter (~linhas 130-155)",
        ]}
        a11y={[
          "role=\"group\" no container, aria-label descrevendo o filtro",
          "Cada pill é <button type=button> com aria-pressed",
          "Mudança anuncia 'N filtros ativos'",
        ]}
        code={`<FilterPillRow
  options={[
    { value: 'debug', label: 'debug' },
    { value: 'info', label: 'info' },
    { value: 'warn', label: 'warn' },
    { value: 'error', label: 'error' },
  ]}
  selected={traceLevels}
  onChange={setTraceLevels}
/>`}
      >
        <PV_FilterPillRow />
      </V4Spec>

      <V4Spec
        id="mol-planstep"
        tier="new"
        name="PlanStepRow"
        level="molecule"
        summary="Step de um plano 3D: número + título + RiskPill à direita. Footer mono com tool_name + status + flag de aprovação. Usado dentro do PlanCard."
        summaryEn="Plan step: number + title + RiskPill. Mono footer: tool_name + status + approval flag."
        props={[
          { name: "step", type: "ModelingPlanStep", desc: "{ seq, title, risk_level, tool_name, status, approval_required }" },
        ]}
        when={[
          "Lista de steps dentro do ModelingPlanCard",
          "Replay de plano histórico (read-only)",
          "Não usar fora do contexto de plano 3D",
        ]}
        refs={[
          "web/src/features/modeling-3d/components/ModelingPlanCard.tsx · li com seq + risk",
          "web/src/features/modeling-3d/types.ts · ModelingPlanStep",
        ]}
        a11y={[
          "<li> dentro de <ol> · ordem semântica importante",
          "RiskPill tem texto além de cor",
          "Status atualizações via aria-live no parent PlanCard",
        ]}
        code={`<ol>
  {plan.steps.map(step => (
    <PlanStepRow key={step.id} step={step} />
  ))}
</ol>`}
      >
        <PV_PlanStepRow />
      </V4Spec>

      <V4Spec
        id="mol-adapterstatus"
        tier="new"
        name="AdapterStatusRow"
        level="molecule"
        summary="Status de um adapter MCP (Blender, Fusion). Nome + pill de estado + footer com transport e detalhe. Estado conectado = ok; outros estados = warn/err."
        summaryEn="MCP adapter status (Blender, Fusion). Name + state pill + footer with transport + detail."
        props={[
          { name: "adapter", type: "ModelingAdapter", desc: "{ software, connected, status, transport, detail }" },
        ]}
        when={[
          "ModelingDiagnosticsModal · seção Adapters",
          "Settings de MCP 3D",
          "Health dashboard (futuro)",
        ]}
        refs={[
          "web/src/features/modeling-3d/components/ModelingDiagnosticsModal.tsx · Adapters section",
        ]}
        a11y={[
          "Estado anunciado em texto, não só cor (conectado/desconectado/erro)",
          "Container é <article> com aria-label \"{software} · {status}\"",
        ]}
        code={`{diagnostics.capabilities.adapters.map(a => (
  <AdapterStatusRow key={a.software} adapter={a} />
))}`}
      >
        <PV_AdapterStatusRow />
      </V4Spec>

      <V4Spec
        id="mol-traceevent"
        tier="new"
        name="TraceEventDetails"
        level="molecule"
        summary="`<details>` collapsible com header (source pill + event_type + duration) e body com message + payload JSON. Click no summary expande. Color do event_type segue level."
        summaryEn="Collapsible <details>: header (source pill + event_type + duration) + body (message + JSON payload). Click summary to expand."
        props={[
          { name: "event", type: "ModelingTraceEvent", desc: "{ source, event_type, level, duration_ms, message, payload, created_at }" },
        ]}
        when={[
          "Lista de eventos no ModelingDiagnosticsModal",
          "Log de execução de plano (futuro)",
          "Audit drill-down (alternativa expansiva ao AuditEventRow)",
        ]}
        refs={[
          "web/src/features/modeling-3d/components/ModelingDiagnosticsModal.tsx · Trace section (~linhas 165-220)",
        ]}
        a11y={[
          "<details>/<summary> nativo → toggle por Enter ou Space",
          "Open state anunciado pelo browser",
          "JSON payload tem max-h-48 + overflow-auto · scrollável com teclado",
        ]}
        code={`{traceQuery.data.map(evt => (
  <TraceEventDetails key={evt.id} event={evt} />
))}`}
      >
        <PV_TraceEventDetails />
      </V4Spec>

      <V4Spec
        id="mol-warningbanner"
        tier="new"
        name="WarningBanner"
        level="molecule"
        summary="Faixa informativa inline para erros/avisos persistentes. Tone ember (warn) ou err (error). Icon shield à esquerda, título + body opcional. Sem botão X — some quando a condição se resolve."
        summaryEn="Inline informative banner for persistent warnings/errors. Tone ember/err. Shield icon left, title + optional body. No close button — dismisses when the condition resolves."
        props={[
          { name: "tone", type: "'ember' | 'err'", desc: "Severidade", default: "ember" },
          { name: "title", type: "string", desc: "Linha principal" },
          { name: "body", type: "node", desc: "Detalhe opcional" },
          { name: "icon", type: "string", desc: "Override do shield", default: "shield" },
        ]}
        when={[
          "ComposerErrorStrip (tone err · acima do composer)",
          "HighRiskBanner dentro do PlanCard (tone ember · acima dos steps)",
          "ChatTitleRequiredDialog · inline validation",
          "Para info passageira, usar Toast em vez",
        ]}
        refs={[
          "web/src/App.tsx · blockedByExecutionConfig (composer)",
          "web/src/features/modeling-3d/components/ModelingPlanCard.tsx · high-risk banner",
          "web/src/features/chat/context-knowledge-bases-modal.tsx · backlog indexing notice",
        ]}
        a11y={[
          "role=\"status\" (warn) ou role=\"alert\" (err)",
          "Não tem botão close — não é dismissable",
          "Icon é decorativo (aria-hidden) · texto carrega tudo",
        ]}
        code={`<WarningBanner tone="err"
  title="Deep Research exige preço do modelo configurado." />

<WarningBanner tone="ember"
  title="2 etapa(s) high-risk nesse plano"
  body="Aprovar autoriza todas, incluindo deleções." />`}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <PV_WarningBanner tone="err" title="Deep Research exige preço do modelo configurado." />
          <PV_WarningBanner tone="ember" title="2 etapa(s) high-risk nesse plano" body="Aprovar autoriza todas, incluindo deleções e operações irreversíveis." />
        </div>
      </V4Spec>

      <V4Spec
        id="mol-metrictile"
        tier="p2"
        name="MetricTile (decisão P2)"
        level="molecule"
        summary="Decisão: MetricTile permanece separado de Stat. Stat é hero (heading display 32px + label); MetricTile é denso (heading 18px + mono label) para dashboards e headers."
        summaryEn="Decision: MetricTile stays separate from Stat. Stat is hero (32px display); MetricTile is dense (18px) for dashboards/headers."
        props={[
          { name: "label", type: "string", desc: "Label mono uppercase" },
          { name: "value", type: "number | string", desc: "Valor (display font)" },
          { name: "tone", type: "'text' | 'ember' | 'azure'", desc: "Cor do valor", default: "text" },
        ]}
        when={[
          "Header de AgentDashboard (count agentes / tokens / chats)",
          "Sidebar info do projeto ativo",
          "Para hero stats (intro page, splash), use Stat",
        ]}
        refs={[
          "web/src/components/app-panels.tsx · Metric (existente)",
        ]}
        a11y={[
          "Number em <strong> ou via aria-label \"{label}: {value}\"",
          "Quando tone ember/azure, contraste suficiente sobre bg-card",
        ]}
        code={`<MetricTile label="chats" value={247} />
<MetricTile label="tokens" value="1.2M" tone="ember" />`}
      >
        <PV_MetricTile />
      </V4Spec>
    </DocSection>
  );
}

Object.assign(window, { V4_MoleculesSection, PV_SearchField, PV_ProviderStatusRow, PV_AuditEventRow, PV_PromptCard, PV_IndexingStatusBadge, PV_FilterPillRow, PV_PlanStepRow, PV_AdapterStatusRow, PV_TraceEventDetails, PV_WarningBanner, PV_MetricTile });
