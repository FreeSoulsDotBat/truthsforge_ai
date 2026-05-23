// Sidebar — slimmer (248px), calmer hierarchy, project tree + history

function Brandmark({ theme }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 11, padding: "20px 16px 16px" }}>
      {/* Symbol — a small flame-anvil mark referencing the brand grafismos */}
      <BrandSymbol size={32} />
      <div style={{ lineHeight: 0.9 }}>
        <div
          style={{
            fontFamily: "var(--font-display)",
            fontSize: 15,
            fontWeight: 400,
            letterSpacing: "0.04em",
            color: "var(--text)",
            textTransform: "uppercase",
          }}
        >
          Truth&rsquo;s
        </div>
        <div
          style={{
            fontFamily: "var(--font-display)",
            fontSize: 15,
            fontWeight: 400,
            letterSpacing: "0.04em",
            color: "var(--ember)",
            textTransform: "uppercase",
            marginTop: 2,
          }}
        >
          Forge
        </div>
      </div>
    </div>
  );
}

// Brand symbol — abstract forge mark (curved arc + spark) inspired by the manual's grafismos
function BrandSymbol({ size = 32, color = "var(--ember)" }) {
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: 8,
        background: "linear-gradient(155deg, color-mix(in srgb, var(--ember) 22%, var(--bg-ink)), var(--bg-ink) 70%)",
        border: "1px solid color-mix(in srgb, var(--ember) 30%, var(--line))",
        boxShadow: "inset 0 0 0 1px color-mix(in srgb, var(--ember) 8%, transparent), 0 0 18px -10px var(--ember-glow)",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        flexShrink: 0,
      }}
    >
      <svg width={size * 0.55} height={size * 0.55} viewBox="0 0 24 24" fill="none">
        {/* Forge arc — curved like the brand grafismo */}
        <path
          d="M4 18 C 4 10, 10 4, 18 6"
          stroke={color}
          strokeWidth="2.2"
          strokeLinecap="round"
          fill="none"
        />
        {/* Spark — small diamond */}
        <path d="M18 14 L19.5 16 L18 18 L16.5 16 Z" fill={color} />
        {/* Anvil base — small horizontal */}
        <path d="M5 20 L13 20" stroke={color} strokeWidth="2" strokeLinecap="round" opacity="0.6" />
      </svg>
    </div>
  );
}

function SearchField({ theme }) {
  return (
    <div style={{ padding: "0 12px 10px" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          height: 34,
          padding: "0 10px",
          borderRadius: 8,
          background: "var(--bg-ink)",
          border: "1px solid var(--line-soft)",
          color: "var(--muted)",
        }}
      >
        <Icon name="search" size={14} />
        <span style={{ flex: 1, fontSize: 12.5 }}>Buscar conversas...</span>
        <KBD>⌘K</KBD>
      </div>
    </div>
  );
}

function NewChatButton() {
  return (
    <div style={{ padding: "0 12px 6px" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          height: 38,
          padding: "0 12px",
          borderRadius: 10,
          background: "color-mix(in oklch, var(--ember) 14%, var(--bg-card))",
          border: "1px solid color-mix(in oklch, var(--ember) 25%, transparent)",
          color: "var(--text)",
          boxShadow: "inset 0 1px 0 color-mix(in oklch, var(--ember) 10%, transparent), 0 8px 24px -16px var(--ember-glow)",
        }}
      >
        <Icon name="plus" size={14} stroke="var(--ember)" />
        <span style={{ flex: 1, fontSize: 13, fontWeight: 500 }}>Nova conversa</span>
        <Mono size={10} color="var(--faint)">
          ⌘N
        </Mono>
      </div>
    </div>
  );
}

function PrimaryNav({ active = "chat" }) {
  const items = [
    { id: "chat", label: "Conversa", icon: "message-square" },
    { id: "agents", label: "Agentes", icon: "users" },
    { id: "projects", label: "Projetos", icon: "folder-tree" },
    { id: "knowledge", label: "Bases", icon: "database" },
    { id: "files", label: "Arquivos", icon: "file-text" },
  ];
  return (
    <div style={{ padding: "10px 6px 4px", display: "flex", flexDirection: "column", gap: 1 }}>
      {items.map((it) => (
        <NavItem key={it.id} icon={<Icon name={it.icon} size={14} />} label={it.label} active={active === it.id} />
      ))}
    </div>
  );
}

function ProjectsTree() {
  return (
    <div style={{ padding: "0 6px" }}>
      <SectionLabel>Projetos</SectionLabel>
      <div style={{ display: "flex", flexDirection: "column", gap: 1, fontSize: 12.5 }}>
        <ProjectRow open name="Forja pessoal" count={12} active />
        <div style={{ paddingLeft: 22, display: "flex", flexDirection: "column", gap: 1 }}>
          <ChatRow label="Pipeline RAG no Postgres" active />
          <ChatRow label="Setup pgvector" />
          <ChatRow label="Backup automático Notion" />
          <FolderRow name="plano-financeiro" count={4} />
          <FolderRow name="estudos" count={8} />
        </div>
        <ProjectRow name="Tese de mestrado" count={28} />
        <ProjectRow name="Cliente · Vasques" count={6} muted />
      </div>
    </div>
  );
}

function ProjectRow({ name, count, open = false, active = false, muted = false }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        height: 28,
        padding: "0 8px",
        borderRadius: 6,
        color: muted ? "var(--faint)" : "var(--text-soft)",
      }}
    >
      <Icon name={open ? "chevron-down" : "chevron-right"} size={12} stroke="var(--faint)" />
      <Icon name="folder" size={13} stroke={active ? "var(--ember)" : "var(--muted)"} />
      <span style={{ flex: 1, fontSize: 12.5, fontWeight: active ? 500 : 400 }}>{name}</span>
      <Mono size={10}>{count}</Mono>
    </div>
  );
}

function FolderRow({ name, count }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, height: 24, padding: "0 8px", color: "var(--muted)" }}>
      <Icon name="hash" size={11} stroke="var(--faint)" />
      <span style={{ flex: 1, fontSize: 12 }}>{name}</span>
      <Mono size={9.5}>{count}</Mono>
    </div>
  );
}

function ChatRow({ label, active = false }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        height: 24,
        padding: "0 8px",
        borderRadius: 5,
        background: active ? "color-mix(in oklch, var(--ember) 8%, transparent)" : "transparent",
        color: active ? "var(--text)" : "var(--text-soft)",
        position: "relative",
      }}
    >
      {active && (
        <span
          style={{
            position: "absolute",
            left: -16,
            top: "50%",
            transform: "translateY(-50%)",
            width: 4,
            height: 4,
            borderRadius: 999,
            background: "var(--ember)",
          }}
        />
      )}
      <span style={{ flex: 1, fontSize: 12, fontWeight: active ? 500 : 400, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</span>
    </div>
  );
}

function HistorySection() {
  const items = [
    { label: "Configurar Tailscale no servidor de casa", time: "ontem" },
    { label: "Auditoria de tokens — gastos OpenAI", time: "ontem" },
    { label: "Migrar base de prompts pra Postgres", time: "3d" },
    { label: "Estudo: orquestração multi-agente", time: "5d" },
    { label: "Refatorar streamChat com SSE robusto", time: "1sem" },
  ];
  return (
    <div style={{ padding: "0 6px" }}>
      <SectionLabel action={<Icon name="more-horizontal" size={12} stroke="var(--faint)" />}>Histórico</SectionLabel>
      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
        {items.map((it) => (
          <div key={it.label} style={{ display: "flex", alignItems: "center", gap: 8, height: 28, padding: "0 8px", borderRadius: 6, color: "var(--text-soft)" }}>
            <span style={{ flex: 1, fontSize: 12, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{it.label}</span>
            <Mono size={9.5} color="var(--faint)">
              {it.time}
            </Mono>
          </div>
        ))}
      </div>
    </div>
  );
}

function SidebarFooter({ theme }) {
  return (
    <div style={{ padding: "12px 14px 14px", borderTop: "1px solid var(--line-soft)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
        <Mono size={10} color="var(--faint)">
          custo · maio
        </Mono>
        <Mono size={10} color="var(--text-soft)">
          R$ 12,84 / 200
        </Mono>
      </div>
      <div style={{ height: 3, background: "var(--bg-ink)", borderRadius: 999, overflow: "hidden", marginBottom: 12 }}>
        <div style={{ width: "6.4%", height: "100%", background: "var(--ember)", boxShadow: "0 0 8px var(--ember-glow)" }} />
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Avatar kind="judite" size={24} theme={theme} />
        <div style={{ flex: 1, lineHeight: 1.2 }}>
          <div style={{ fontSize: 12, color: "var(--text)" }}>JUDITE</div>
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <Pulse color="var(--ok)" size={5} />
            <Mono size={9.5} color="var(--muted)">
              online · gpt-4o
            </Mono>
          </div>
        </div>
        <Icon name="settings" size={14} stroke="var(--muted)" />
      </div>
    </div>
  );
}

function Sidebar({ theme, active = "chat" }) {
  window.__currentTheme = theme;
  return (
    <aside
      style={{
        width: 248,
        flexShrink: 0,
        background: "var(--bg-ink)",
        borderRight: "1px solid var(--line-soft)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
      }}
    >
      <Brandmark theme={theme} />
      <SearchField theme={theme} />
      <NewChatButton />
      <PrimaryNav active={active} />
      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <ProjectsTree />
        <HistorySection />
      </div>
      <SidebarFooter theme={theme} />
    </aside>
  );
}

// Right dock — 56px rail with panel toggles
function Dock({ active = "contexto" }) {
  const items = [
    { id: "contexto", icon: "activity", label: "Contexto" },
    { id: "infra", icon: "server", label: "Infra" },
    { id: "auditoria", icon: "shield", label: "Auditoria" },
    { id: "prompts", icon: "library", label: "Prompts" },
    { id: "config", icon: "settings", label: "Configurações" },
  ];
  return (
    <div
      style={{
        width: 56,
        flexShrink: 0,
        background: "var(--bg-ink)",
        borderLeft: "1px solid var(--line-soft)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "18px 0",
        gap: 6,
      }}
    >
      {items.map((it) => {
        const isActive = active === it.id;
        return (
          <div
            key={it.id}
            style={{
              width: 38,
              height: 38,
              borderRadius: 10,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: isActive ? "var(--ember)" : "var(--muted)",
              background: isActive ? "color-mix(in oklch, var(--ember) 12%, transparent)" : "transparent",
              border: isActive ? "1px solid color-mix(in oklch, var(--ember) 25%, transparent)" : "1px solid transparent",
              position: "relative",
            }}
            title={it.label}
          >
            <Icon name={it.icon} size={15} />
            {isActive && (
              <span
                style={{
                  position: "absolute",
                  right: -3,
                  top: "50%",
                  transform: "translateY(-50%)",
                  width: 3,
                  height: 14,
                  borderRadius: 2,
                  background: "var(--ember)",
                }}
              />
            )}
          </div>
        );
      })}
      <div style={{ flex: 1 }} />
      <div style={{ width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--faint)" }}>
        <Pulse color="var(--ok)" size={5} />
      </div>
    </div>
  );
}

Object.assign(window, { Sidebar, Dock, BrandSymbol, Brandmark });
