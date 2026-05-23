// Modals & dialogs — applied to the brand system

function ModalShell({ width = 480, eyebrow, title, accent = "ember", children, footer, danger = false }) {
  const accentColor = danger ? "var(--err)" : accent === "amethyst" ? "var(--amethyst)" : accent === "azure" ? "var(--azure)" : "var(--ember)";
  const accentGlow = danger ? "rgba(255, 90, 74, 0.25)" : accent === "amethyst" ? "var(--amethyst-glow)" : accent === "azure" ? "var(--azure-glow)" : "var(--ember-glow)";
  return (
    <div
      style={{
        width,
        background: "var(--bg-elev)",
        border: "1px solid var(--line)",
        borderRadius: "var(--radius-lg)",
        boxShadow: `0 24px 80px -24px ${accentGlow}, 0 1px 0 0 color-mix(in srgb, ${accentColor} 12%, transparent)`,
        overflow: "hidden",
        fontFamily: "var(--font-text)",
        position: "relative",
      }}
    >
      {/* Accent stripe */}
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: accentColor, boxShadow: `0 0 12px ${accentGlow}` }} />
      <div style={{ padding: "22px 26px 18px", borderBottom: "1px solid var(--line-soft)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            {eyebrow && (
              <Mono size={10} color={accentColor} style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>
                {eyebrow}
              </Mono>
            )}
            <h2
              style={{
                margin: eyebrow ? "8px 0 0" : 0,
                fontFamily: "var(--font-display)",
                fontSize: 22,
                fontWeight: 400,
                letterSpacing: "0.01em",
                textTransform: "uppercase",
                color: "var(--text)",
                lineHeight: 1.05,
              }}
            >
              {title}
            </h2>
          </div>
          <button
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              background: "transparent",
              border: "1px solid var(--line-soft)",
              color: "var(--muted)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            <Icon name="x" size={13} />
          </button>
        </div>
      </div>
      <div style={{ padding: "22px 26px" }}>{children}</div>
      {footer && (
        <div style={{ padding: "16px 24px", borderTop: "1px solid var(--line-soft)", background: "color-mix(in srgb, var(--bg-ink) 50%, var(--bg-elev))", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          {footer}
        </div>
      )}
    </div>
  );
}

function ModalButton({ tone = "neutral", icon, label, danger = false }) {
  const tones = {
    primary: { bg: "var(--ember)", color: "var(--ember-ink)", border: "transparent", shadow: "0 8px 22px -10px var(--ember-glow)" },
    amethyst: { bg: "var(--amethyst)", color: "#ffffff", border: "transparent", shadow: "0 8px 22px -10px var(--amethyst-glow)" },
    danger: { bg: "var(--err)", color: "#ffffff", border: "transparent", shadow: "0 8px 22px -10px rgba(255,90,74,0.4)" },
    neutral: { bg: "var(--bg-card)", color: "var(--text)", border: "var(--line)", shadow: "none" },
    ghost: { bg: "transparent", color: "var(--text-soft)", border: "var(--line-soft)", shadow: "none" },
  };
  const t = danger ? tones.danger : tones[tone] || tones.neutral;
  return (
    <button
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        height: 36,
        padding: "0 16px",
        borderRadius: 10,
        background: t.bg,
        color: t.color,
        border: `1px solid ${t.border}`,
        boxShadow: t.shadow,
        fontFamily: "var(--font-text)",
        fontSize: 13,
        fontWeight: 500,
        cursor: "pointer",
        whiteSpace: "nowrap",
      }}
    >
      {icon && <Icon name={icon} size={13} />}
      {label}
    </button>
  );
}

function FieldLabel({ children }) {
  return (
    <div style={{ marginBottom: 6 }}>
      <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>
        {children}
      </Mono>
    </div>
  );
}

function TextField({ label, value, placeholder, mono = false, accent }) {
  return (
    <div>
      {label && <FieldLabel>{label}</FieldLabel>}
      <div
        style={{
          height: 38,
          padding: "0 12px",
          borderRadius: 10,
          background: "var(--bg-ink)",
          border: `1px solid ${accent ? "color-mix(in srgb, var(--ember) 35%, var(--line))" : "var(--line)"}`,
          boxShadow: accent ? "0 0 0 3px color-mix(in srgb, var(--ember) 10%, transparent)" : "none",
          display: "flex",
          alignItems: "center",
          fontFamily: mono ? "var(--font-mono)" : "var(--font-text)",
          fontSize: 13,
          color: value ? "var(--text)" : "var(--muted)",
        }}
      >
        {value || placeholder}
        {accent && (
          <span style={{ marginLeft: "auto", display: "inline-block", width: 1.5, height: 16, background: "var(--ember)", animation: "tfBlink 1s infinite" }} />
        )}
      </div>
    </div>
  );
}

// 1) Confirm delete (destructive)
function ConfirmDeleteModal() {
  return (
    <ModalShell
      width={460}
      eyebrow="EXCLUIR · DESTRUTIVO"
      title="Apagar a base?"
      danger
      footer={
        <>
          <ModalButton tone="ghost" label="Cancelar" />
          <ModalButton danger icon="x" label="Apagar base" />
        </>
      }
    >
      <p style={{ margin: 0, fontSize: 14, color: "var(--text-soft)", lineHeight: 1.6 }}>
        Você vai apagar a base <strong style={{ color: "var(--text)" }}>"RAG · documentação pessoal"</strong>.
      </p>
      <div style={{ marginTop: 14, padding: "12px 14px", background: "color-mix(in srgb, var(--err) 8%, var(--bg-card))", border: "1px solid color-mix(in srgb, var(--err) 25%, transparent)", borderRadius: 10 }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
          <Icon name="shield" size={14} stroke="var(--err)" />
          <div style={{ flex: 1, fontSize: 12.5, color: "var(--text-soft)", lineHeight: 1.55 }}>
            Os <strong style={{ color: "var(--text)" }}>124 documentos</strong> e <strong style={{ color: "var(--text)" }}>3.4k chunks</strong> não serão apagados — só perdem a curadoria. JUDITE deixa de citar essa base nos próximos turnos. <span style={{ color: "var(--muted)" }}>Não há desfazer.</span>
          </div>
        </div>
      </div>
      <div style={{ marginTop: 16 }}>
        <FieldLabel>Confirme digitando o nome</FieldLabel>
        <TextField placeholder="RAG · documentação pessoal" />
      </div>
    </ModalShell>
  );
}

// 2) Duplicate file — two-column compare (existing pattern)
function DuplicateFileModal() {
  return (
    <ModalShell
      width={580}
      eyebrow="ARQUIVO DUPLICADO"
      title="Já existe um arquivo igual"
      footer={
        <>
          <ModalButton tone="ghost" label="Cancelar" />
          <ModalButton tone="neutral" label="Enviar cópia" />
          <ModalButton tone="primary" icon="check" label="Usar existente" />
        </>
      }
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <FileCompareCard kind="upload" name="schema-rag-v3.sql" meta="12 KB · agora" />
        <FileCompareCard kind="exists" name="schema-rag-v3.sql" meta="12 KB · há 4 dias · forja-pessoal" />
      </div>
      <p style={{ margin: "16px 0 0", fontSize: 12.5, color: "var(--muted)", lineHeight: 1.55 }}>
        O hash bate. Você pode reaproveitar o arquivo existente (recomendado) ou enviar mesmo assim — o servidor salva como <span style={{ fontFamily: "var(--font-mono)", color: "var(--text)", fontSize: 12 }}>schema-rag-v3 (1).sql</span>.
      </p>
    </ModalShell>
  );
}

function FileCompareCard({ kind, name, meta }) {
  const isUpload = kind === "upload";
  return (
    <div style={{ padding: "14px 14px", borderRadius: 10, background: "var(--bg-card)", border: `1px solid ${isUpload ? "color-mix(in srgb, var(--ember) 25%, transparent)" : "var(--line-soft)"}` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <Mono size={9.5} color={isUpload ? "var(--ember)" : "var(--faint)"} style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>
          {isUpload ? "novo envio" : "existente"}
        </Mono>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <FileIcon type="sql" />
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13, color: "var(--text)", fontWeight: 500 }}>{name}</div>
          <Mono size={10} color="var(--muted)" style={{ marginTop: 2, display: "block" }}>
            {meta}
          </Mono>
        </div>
      </div>
    </div>
  );
}

// 3) Chat title required
function TitleRequiredModal() {
  return (
    <ModalShell
      width={460}
      eyebrow="TÍTULO OBRIGATÓRIO"
      title="Dê um nome a essa conversa"
      footer={
        <>
          <ModalButton tone="ghost" label="Cancelar" />
          <ModalButton tone="primary" icon="check" label="Salvar e enviar" />
        </>
      }
    >
      <p style={{ margin: "0 0 16px", fontSize: 13.5, color: "var(--text-soft)", lineHeight: 1.55 }}>
        Conversas no projeto <strong style={{ color: "var(--text)" }}>"Forja pessoal"</strong> precisam de título. JUDITE pode sugerir uma a partir da sua primeira mensagem.
      </p>
      <TextField label="Título" value="Pipeline RAG no Postgres" accent />
      <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 6 }}>
        <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>
          sugestões de JUDITE
        </Mono>
        {["Configurar pgvector e busca híbrida", "RAG no Postgres — schema + auditoria", "Setup de busca semântica no banco"].map((s) => (
          <div key={s} style={{ padding: "8px 12px", borderRadius: 8, background: "var(--bg-card)", border: "1px solid var(--line-soft)", fontSize: 12.5, color: "var(--text-soft)", display: "flex", alignItems: "center", gap: 8 }}>
            <Icon name="sparkles" size={11} stroke="var(--ember)" />
            <span style={{ flex: 1 }}>{s}</span>
            <Mono size={9.5} color="var(--faint)">usar</Mono>
          </div>
        ))}
      </div>
    </ModalShell>
  );
}

// 4) Knowledge bases picker
function KnowledgePickerModal() {
  const bases = [
    { name: "RAG · documentação pessoal", docs: 124, selected: true, color: "var(--ember)" },
    { name: "Estudos · sistemas distribuídos", docs: 48, selected: true, color: "var(--amethyst)" },
    { name: "Direito · jurisprudência", docs: 211, color: "var(--azure)" },
    { name: "Receitas e despensa", docs: 36, color: "#5acf8c" },
    { name: "Snippets · operacional", docs: 18, color: "var(--muted)" },
  ];
  return (
    <ModalShell
      width={560}
      accent="amethyst"
      eyebrow="CONTEXTO · BASES"
      title="O que JUDITE pode citar?"
      footer={
        <>
          <Mono size={10} color="var(--muted)" style={{ marginRight: "auto", alignSelf: "center" }}>
            2 bases · ~3.5k chunks elegíveis
          </Mono>
          <ModalButton tone="ghost" label="Cancelar" />
          <ModalButton tone="primary" icon="check" label="Aplicar" />
        </>
      }
    >
      <p style={{ margin: "0 0 16px", fontSize: 13, color: "var(--muted)", lineHeight: 1.55 }}>
        Marque as bases que JUDITE pode consultar nessa conversa. Você pode mudar a qualquer momento.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 320, overflow: "auto" }}>
        {bases.map((b) => (
          <PickerRow key={b.name} {...b} />
        ))}
      </div>
    </ModalShell>
  );
}

function PickerRow({ name, docs, selected, color }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "10px 12px",
        borderRadius: 10,
        background: selected ? "color-mix(in srgb, var(--ember) 6%, var(--bg-card))" : "var(--bg-card)",
        border: selected ? "1px solid color-mix(in srgb, var(--ember) 25%, transparent)" : "1px solid var(--line-soft)",
      }}
    >
      <span
        style={{
          width: 16,
          height: 16,
          borderRadius: 4,
          border: `1.5px solid ${selected ? "var(--ember)" : "var(--line)"}`,
          background: selected ? "var(--ember)" : "transparent",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {selected && <Icon name="check" size={11} stroke="var(--ember-ink)" strokeWidth={3} />}
      </span>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: color, transform: "rotate(45deg)", boxShadow: selected ? `0 0 8px ${color}` : "none", flexShrink: 0 }} />
      <span style={{ flex: 1, fontSize: 13, color: "var(--text)" }}>{name}</span>
      <Mono size={10} color="var(--muted)">{docs} docs</Mono>
    </div>
  );
}

// 5) MCP 3D enable
function MCP3DModal() {
  return (
    <ModalShell
      width={500}
      accent="amethyst"
      eyebrow="MCP 3D · BLENDER / FUSION"
      title="Ativar modelagem 3D?"
      footer={
        <>
          <ModalButton tone="ghost" label="Agora não" />
          <ModalButton tone="amethyst" icon="boxes" label="Ativar nessa conversa" />
        </>
      }
    >
      <p style={{ margin: 0, fontSize: 13.5, color: "var(--text-soft)", lineHeight: 1.6 }}>
        Quando ativo, JUDITE gera um <strong style={{ color: "var(--text)" }}>plano estruturado</strong> e o envia para o Blender ou Fusion via MCP. Você aprova passo a passo — nada roda sem seu OK.
      </p>
      <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <SoftwareCard name="Blender" status="conectado · 4.2" icon="boxes" active />
        <SoftwareCard name="Fusion 360" status="aguardando bridge" icon="boxes" />
      </div>
      <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", background: "color-mix(in srgb, var(--amethyst) 6%, var(--bg-card))", border: "1px solid color-mix(in srgb, var(--amethyst) 25%, transparent)", borderRadius: 10 }}>
        <Icon name="shield" size={14} stroke="var(--amethyst)" />
        <div style={{ flex: 1, fontSize: 12, color: "var(--text-soft)", lineHeight: 1.5 }}>
          Reasoning longo, deep research e imagem ficam <span style={{ color: "var(--muted)" }}>indisponíveis</span> nesse modo. JUDITE foca só no plano.
        </div>
      </div>
    </ModalShell>
  );
}

function SoftwareCard({ name, status, icon, active }) {
  return (
    <div style={{ padding: "12px 14px", borderRadius: 10, background: "var(--bg-card)", border: active ? "1px solid color-mix(in srgb, var(--amethyst) 30%, transparent)" : "1px solid var(--line-soft)", boxShadow: active ? "0 8px 22px -14px var(--amethyst-glow)" : "none" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <Icon name={icon} size={14} stroke={active ? "var(--amethyst)" : "var(--muted)"} />
        <span style={{ fontSize: 13.5, color: "var(--text)", fontWeight: 500 }}>{name}</span>
        {active && <Pulse color="var(--amethyst)" size={5} />}
      </div>
      <Mono size={10} color={active ? "var(--amethyst)" : "var(--faint)"}>
        {status}
      </Mono>
    </div>
  );
}

// 6) Agent edit (compact sheet)
function AgentEditModal() {
  return (
    <ModalShell
      width={620}
      eyebrow="AGENTE · CONFIGURAÇÃO"
      title="Editar JUDITE"
      footer={
        <>
          <ModalButton tone="ghost" label="Cancelar" />
          <ModalButton tone="primary" icon="check" label="Salvar agente" />
        </>
      }
    >
      <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 18 }}>
        <Avatar kind="judite" size={64} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <TextField label="Nome" value="JUDITE" />
          <TextField label="Papel" value="Orquestradora" />
          <div style={{ gridColumn: "span 2" }}>
            <TextField label="Modelo · provider/id" value="openai · gpt-4o" mono />
          </div>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <FieldLabel>System prompt</FieldLabel>
        <div
          style={{
            padding: "12px 14px",
            borderRadius: 10,
            background: "var(--bg-ink)",
            border: "1px solid var(--line)",
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            color: "var(--text-soft)",
            lineHeight: 1.6,
            minHeight: 92,
          }}
        >
          <span style={{ color: "var(--muted)" }}>// Você é JUDITE — orquestradora local-first.</span><br />
          Seu papel é coordenar especialistas, decidir handoffs e<br />
          manter memória de longo prazo. <span style={{ color: "var(--ember)" }}>Sempre em pt-BR.</span>
        </div>
      </div>

      <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
        <MiniToggle label="Multiagente" hint="2 apoios elegíveis" on />
        <MiniToggle label="MCP 3D" hint="Blender · Fusion" />
        <MiniToggle label="Custo · alerta" hint="80% do limite" on />
      </div>
    </ModalShell>
  );
}

function MiniToggle({ label, hint, on = false }) {
  return (
    <div style={{ padding: "10px 12px", borderRadius: 10, background: "var(--bg-card)", border: "1px solid var(--line-soft)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <span style={{ fontSize: 12.5, color: "var(--text)" }}>{label}</span>
        <span style={{ width: 26, height: 14, borderRadius: 999, background: on ? "var(--ember)" : "var(--bg-ink)", border: `1px solid ${on ? "var(--ember)" : "var(--line)"}`, position: "relative", flexShrink: 0 }}>
          <span style={{ position: "absolute", top: 1, left: on ? 12 : 1, width: 10, height: 10, borderRadius: 999, background: on ? "var(--ember-ink)" : "var(--muted)", transition: "left 0.15s" }} />
        </span>
      </div>
      <Mono size={9.5} color="var(--faint)" style={{ marginTop: 4, display: "block" }}>
        {hint}
      </Mono>
    </div>
  );
}

// Group: all modals on a scene with a dim backdrop
function ModalsScene({ theme }) {
  return (
    <div style={{ ...themeVars(theme), width: "100%", height: "100%", background: "var(--bg-ink)", padding: "40px", overflow: "auto", fontFamily: "var(--font-text)", position: "relative" }}>
      {/* subtle backdrop grid */}
      <div style={{ position: "absolute", inset: 0, backgroundImage: "radial-gradient(circle at 1px 1px, var(--line-soft) 1px, transparent 0)", backgroundSize: "32px 32px", opacity: 0.4, pointerEvents: "none" }} />
      <div style={{ position: "relative", display: "flex", flexDirection: "column", gap: 28 }}>
        <div>
          <Mono size={11} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.2em" }}>
            sistema · modais e diálogos
          </Mono>
          <h2 style={{ margin: "10px 0 0", fontFamily: "var(--font-display)", fontSize: 32, fontWeight: 400, letterSpacing: "0.01em", textTransform: "uppercase", color: "var(--text)" }}>
            Diálogos
          </h2>
          <p style={{ margin: "8px 0 0", fontSize: 13.5, color: "var(--muted)", maxWidth: 520, lineHeight: 1.55 }}>
            Cada modal é uma decisão — não um interrúpicio. Cabeçalho com eyebrow, corpo respirado, ações sempre na ordem cancelar → confirmar.
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28, alignItems: "start" }}>
          <ConfirmDeleteModal />
          <TitleRequiredModal />
          <DuplicateFileModal />
          <KnowledgePickerModal />
          <MCP3DModal />
          <AgentEditModal />
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  ModalShell, ModalsScene,
  ConfirmDeleteModal, DuplicateFileModal, TitleRequiredModal, KnowledgePickerModal, MCP3DModal, AgentEditModal,
  ModalButton, TextField, FieldLabel,
});
