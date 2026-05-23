// v4 — New & gap-filling Atoms
// Tier: P1 (Textarea, Select, NumberInput, ProgressBar, HelperIcon)
//       NEW (RiskPill, CopyableCode)

// ─── Preview primitives ──────────────────────────────────────────────────────

function PV_Textarea({ rows = 3, value, placeholder, mono = false }) {
  return (
    <textarea
      readOnly
      rows={rows}
      defaultValue={value}
      placeholder={placeholder}
      style={{
        width: 260, minHeight: 40 + (rows - 1) * 22, padding: "10px 12px",
        background: "var(--bg-ink)", border: "1px solid var(--line-soft)",
        borderRadius: 10, color: "var(--text)",
        fontFamily: mono ? "var(--font-mono)" : "var(--font-text)", fontSize: 13,
        resize: "vertical", outline: "none",
      }}
    />
  );
}

function PV_Select({ value, options = [], width = 180, disabled = false, size = "md" }) {
  const heights = { sm: 28, md: 36, lg: 40 };
  return (
    <div style={{ position: "relative", width, opacity: disabled ? 0.5 : 1 }}>
      <div style={{
        height: heights[size], padding: "0 32px 0 12px",
        background: "var(--bg-ink)", border: "1px solid var(--line-soft)", borderRadius: 8,
        display: "flex", alignItems: "center", color: "var(--text)", fontSize: size === "sm" ? 12 : 13,
      }}>
        {value}
      </div>
      <span style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", pointerEvents: "none", color: "var(--muted)" }}>
        <Icon name="chevron-down" size={12} stroke="var(--muted)" />
      </span>
    </div>
  );
}

function PV_NumberInput({ value, suffix, error = false }) {
  const color = error ? "var(--err)" : "var(--line-soft)";
  return (
    <div style={{ position: "relative", width: 140 }}>
      <div style={{
        height: 36, padding: "0 12px",
        background: "var(--bg-ink)", border: `1px solid ${color}`, borderRadius: 8,
        display: "flex", alignItems: "center", color: "var(--text)",
        fontFamily: "var(--font-mono)", fontSize: 13,
      }}>
        {value}
      </div>
      {suffix && (
        <span style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)", fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--faint)" }}>
          {suffix}
        </span>
      )}
    </div>
  );
}

function PV_ProgressBar({ value, indeterminate = false, tone = "ember", width = 240 }) {
  const color = tone === "amethyst" ? "var(--amethyst)" : tone === "ok" ? "var(--ok)" : "var(--ember)";
  return (
    <div style={{ width, height: 4, background: "var(--bg-ink)", border: "1px solid var(--line-soft)", borderRadius: 2, overflow: "hidden", position: "relative" }}>
      {indeterminate ? (
        <div style={{
          position: "absolute", inset: 0,
          background: `linear-gradient(90deg, transparent, ${color}, transparent)`,
          backgroundSize: "200% 100%",
          animation: "tfShimmer 1.6s linear infinite",
        }} />
      ) : (
        <div style={{ width: `${value}%`, height: "100%", background: color, transition: "width 250ms ease-out", boxShadow: `0 0 8px ${color}` }} />
      )}
    </div>
  );
}

function PV_HelperIcon() {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--muted)" }}>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.12em" }}>temperature</span>
      <Icon name="info" size={12} stroke="var(--ember)" />
    </span>
  );
}

function PV_RiskPill({ level }) {
  const styles = {
    low:    { color: "var(--ok)",       label: "low",    bg: "color-mix(in srgb, var(--ok) 14%, transparent)" },
    medium: { color: "var(--ember)",    label: "medium", bg: "color-mix(in srgb, var(--ember) 14%, transparent)" },
    high:   { color: "var(--err)",      label: "high",   bg: "color-mix(in srgb, var(--err) 14%, transparent)" },
  };
  const s = styles[level];
  return (
    <span style={{
      padding: "3px 9px", borderRadius: 4, background: s.bg, color: s.color,
      border: `1px solid color-mix(in srgb, ${s.color} 35%, transparent)`,
      fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.1em",
      fontWeight: 600,
    }}>{s.label}</span>
  );
}

function PV_CopyableCode({ children }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      padding: "3px 8px", borderRadius: 4, background: "var(--bg-card)", border: "1px solid var(--line-soft)",
      fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--text-soft)", cursor: "pointer",
    }}>
      {children}
      <Icon name="copy" size={10} stroke="var(--faint)" />
    </span>
  );
}

// ─── The atoms section ──────────────────────────────────────────────────────

function V4_AtomsSection() {
  return (
    <DocSection
      id="v4-atoms"
      eyebrow="03 · Átomos"
      title="Átomos"
      intro="Peças irredutíveis. Cada átomo declara sua geometria, props, estados e notas de a11y — é a forma canônica."
    >
      <V4Spec
        id="atom-textarea"
        tier="p1"
        name="Textarea"
        level="atom"
        summary="Campo de texto multilinha. Auto-grow opcional (até max-rows). Variante mono para conteúdo técnico (system prompt, código). Resize-y opt-in."
        summaryEn="Multiline text input. Optional auto-grow up to max-rows. Mono variant for technical content. Opt-in vertical resize."
        props={[
          { name: "value", type: "string", desc: "Valor controlado" },
          { name: "rows", type: "number", desc: "Linhas iniciais", default: "3" },
          { name: "maxRows", type: "number", desc: "Limite para auto-grow", default: "10" },
          { name: "mono", type: "boolean", desc: "Usa font-mono" },
          { name: "resize", type: "'none' | 'vertical'", desc: "Permite arrastar para crescer", default: "vertical" },
          { name: "placeholder", type: "string", desc: "Texto vazio" },
          { name: "error", type: "boolean", desc: "Estado de erro · border-err" },
        ]}
        when={[
          "Composer (sem max-rows fixo, auto-grow ilimitado)",
          "System prompt do agente (mono · max-rows 12)",
          "Descrição do agente (default · max-rows 6)",
          "Conteúdo Markdown ao indexar (mono · max-rows 20 · resize-y)",
        ]}
        refs={[
          "web/src/App.tsx · composer (~linha 3032)",
          "web/src/features/dashboard/dashboard-sections.tsx · system_prompt, description",
          "web/src/features/modeling-3d/components/ModelingPlanCard.tsx · reject reason",
        ]}
        a11y={[
          "aria-invalid quando error · descrito por <hint /> via aria-describedby",
          "Tab navega in/out · Shift+Tab para sair sem submeter",
          "Enter NÃO submete por default — exceto no composer (Cmd/Ctrl+Enter)",
        ]}
        migration={<>O codebase tem várias textareas inline com altura/padding/resize diferentes. Centralizar em <TKN>web/src/components/ui/Textarea.tsx</TKN> seguindo esta spec.</>}
        code={`<Textarea
  rows={3} maxRows={10}
  value={value}
  placeholder="Descreva o agente..."
/>

<Textarea mono rows={6}
  value={systemPrompt}
  resize="vertical" />`}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <PV_Textarea rows={2} value="Descreva o agente..." />
          <PV_Textarea rows={4} mono value={`Você é JUDITE, agente de
modelagem 3D allowlistada.`} />
        </div>
      </V4Spec>

      <V4Spec
        id="atom-select"
        tier="p1"
        name="Select"
        level="atom"
        summary="Dropdown nativo estilizado em 3 tamanhos. Native por padrão (a11y grátis); variante custom só quando precisa de search ou rich options (vira organismo)."
        summaryEn="Styled native dropdown in 3 sizes. Native by default (free a11y); custom variant only when search or rich options are needed (then it's an organism)."
        props={[
          { name: "value", type: "string", desc: "Valor atual" },
          { name: "options", type: "Option[]", desc: "Lista de { value, label }" },
          { name: "size", type: "'sm' | 'md' | 'lg'", desc: "Altura · sm 28 / md 36 / lg 40", default: "md" },
          { name: "disabled", type: "boolean", desc: "Estado desabilitado" },
          { name: "error", type: "boolean", desc: "Border vermelho" },
        ]}
        when={[
          "Provider/Model picker no AgentDashboard (md)",
          "Folder picker no ProjectExplorer ChatRow (sm)",
          "EnableModeling3DDialog · software (md)",
          "Se precisa de busca: usar CommandPalette ou MentionPopover",
        ]}
        refs={[
          "frames/forms.jsx · existe no kit",
          "web/src/components/app-form.tsx · AgentLLMSelect",
          "web/src/features/sidebar/project-explorer-section.tsx · folder picker (h-7)",
        ]}
        a11y={[
          "Usa <select> nativo — herda comportamento OS (espaço abre, setas navegam)",
          "Label sempre associada via <label> ou aria-labelledby",
          "Disabled visualmente distinto: opacity 0.5 + cursor-not-allowed",
        ]}
        code={`<Select value={provider} size="md"
  options={[
    { value: 'openai', label: 'OpenAI' },
    { value: 'anthropic', label: 'Anthropic' },
  ]}
  onChange={setProvider} />`}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-start" }}>
          <PV_Select size="sm" value="rag/pessoal" />
          <PV_Select size="md" value="gpt-4o" />
          <PV_Select size="lg" value="anthropic" />
          <PV_Select size="md" value="—" disabled />
        </div>
      </V4Spec>

      <V4Spec
        id="atom-numberinput"
        tier="p1"
        name="NumberInput"
        level="atom"
        summary="Aceita rascunhos numéricos incompletos durante a digitação (`0.`, `-`, `1e`); normaliza on blur. Sufixo opcional para unidade. Pattern de parse documentado no shared/utils."
        summaryEn="Accepts incomplete numeric drafts while typing; normalizes on blur. Optional unit suffix."
        props={[
          { name: "value", type: "number | null", desc: "Valor commitado" },
          { name: "suffix", type: "string", desc: "Unidade à direita (`tok`, `°C`, `%`)" },
          { name: "step", type: "number", desc: "Granularidade", default: "1" },
          { name: "min/max", type: "number", desc: "Limites opcionais" },
          { name: "error", type: "boolean", desc: "Quando draft não casa com pattern" },
        ]}
        when={[
          "temperature, top_p, max_tokens, budget — AgentDashboard",
          "max_documents, max_chunks_per_document — KnowledgeDashboard",
          "Nunca use <input type=number> direto — perde o draft incompleto",
        ]}
        refs={[
          "frames/forms.jsx · NumericDraftInput",
          "web/src/components/app-form.tsx · AgentLLMNumberInput",
          "web/src/shared/utils/common.ts · normalizeNumberDraft, numericDraftPattern, incompleteNumericDrafts",
        ]}
        a11y={[
          "inputMode=\"decimal\" → teclado numérico mobile",
          "aria-invalid quando error",
          "Suffix é decorativo · não anunciado pelo screen reader (incluir no label)",
        ]}
        code={`<NumberInput
  value={agent.temperature}
  suffix="°"
  min={0} max={2} step={0.05}
  onChange={(v) => update('temperature', v)}
/>`}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-start" }}>
          <PV_NumberInput value="0.7" suffix="°" />
          <PV_NumberInput value="4096" suffix="tok" />
          <PV_NumberInput value="0." suffix="°" />
          <PV_NumberInput value="—" suffix="bad" error />
        </div>
      </V4Spec>

      <V4Spec
        id="atom-progressbar"
        tier="p1"
        name="ProgressBar"
        level="atom"
        summary="Barra linear de progresso. Altura 4px, radius 2. Variante determinate (value 0-100) e indeterminate (shimmer). Tone ember (default), ok (concluído), amethyst (3D/long-running)."
        summaryEn="Linear progress bar. 4px height, radius 2. Determinate (value 0-100) and indeterminate (shimmer) variants."
        props={[
          { name: "value", type: "number", desc: "0-100 · ignorado se indeterminate" },
          { name: "indeterminate", type: "boolean", desc: "Modo shimmer infinito" },
          { name: "tone", type: "'ember' | 'amethyst' | 'ok'", desc: "Cor do fill", default: "ember" },
        ]}
        when={[
          "ChatGPTImportProgressCard (determinate · ember)",
          "ImageUploading (determinate · ember)",
          "Indexação em massa (indeterminate · amethyst)",
          "Job concluído: tone ok 100%",
        ]}
        refs={[
          "web/src/features/dashboard/dashboard-sections.tsx · ~linhas 1626-1640 (ChatGPT import)",
          "frames/image-preview.jsx · ImageUploading",
        ]}
        a11y={[
          "role=\"progressbar\" + aria-valuenow / aria-valuemin / aria-valuemax",
          "Indeterminate omite aria-valuenow",
          "Label visível ou aria-label obrigatório (\"Importando…\")",
        ]}
        code={`<ProgressBar value={62} tone="ember" />
<ProgressBar indeterminate tone="amethyst" />
<ProgressBar value={100} tone="ok" />`}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <PV_ProgressBar value={62} />
          <PV_ProgressBar indeterminate tone="amethyst" />
          <PV_ProgressBar value={100} tone="ok" />
        </div>
      </V4Spec>

      <V4Spec
        id="atom-helpericon"
        tier="p1"
        name="HelperIcon"
        level="atom"
        summary="Ícone info 12-13px que dispara o Tooltip on hover/focus. Inverso do Tooltip — é o gatilho, não o conteúdo. Cor muted → ember on hover."
        summaryEn="13px info icon that triggers Tooltip on hover/focus. Inverse of Tooltip — the trigger, not the content."
        props={[
          { name: "tip", type: "string", desc: "Texto do tooltip (obrigatório)" },
          { name: "size", type: "number", desc: "Tamanho em px", default: "13" },
        ]}
        when={[
          "Em quase todo Field técnico do dashboard de agente",
          "Ao lado de SubFieldLabel (form denso · padrão)",
          "NUNCA em campos triviais (`Nome`, `Email`) — só onde precisa de explicação",
        ]}
        refs={[
          "web/src/components/app-form.tsx · InfoTip, SubFieldLabel",
        ]}
        a11y={[
          "tabIndex={0} → ganha foco com teclado",
          "aria-label === tip → screen reader anuncia direto",
          "Tooltip aparece on hover E on focus (não só hover)",
        ]}
        code={`<label>
  <SubFieldLabel text="Temperature" tip="Aleatoriedade · 0-2. Padrão 0.7." />
  <NumberInput value={t} suffix="°" />
</label>`}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-start" }}>
          <PV_HelperIcon />
          <div style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--muted)" }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.12em" }}>multiagente</span>
            <Icon name="info" size={12} stroke="var(--muted)" />
          </div>
        </div>
      </V4Spec>

      <V4Spec
        id="atom-riskpill"
        tier="new"
        name="RiskPill"
        level="atom"
        summary="Pill de nível de risco com 3 tons: low (ok), medium (ember), high (err). Mono uppercase, padding apertado. Variante semântica do Tag, mas com mapeamento fixo level → cor."
        summaryEn="Risk-level pill: low/medium/high mapped to ok/ember/err. Semantic variant of Tag with fixed level→color mapping."
        props={[
          { name: "level", type: "'low' | 'medium' | 'high'", desc: "Nível de risco" },
        ]}
        when={[
          "Em cada PlanStep do ModelingPlanCard",
          "Em PrintabilityReport (severity)",
          "Em qualquer lugar que `step.risk_level` apareça",
          "Não usar fora desse contexto — para outros badges, use Tag",
        ]}
        refs={[
          "web/src/features/modeling-3d/components/ModelingPlanCard.tsx · RISK_BADGE_CLASS",
          "web/src/features/modeling-3d/types.ts · ModelingRiskLevel",
        ]}
        a11y={[
          "aria-label=\"risco {level}\" para clarificar fora de contexto",
          "Não confiar só na cor (high vs medium): texto sempre presente",
        ]}
        code={`<RiskPill level={step.risk_level} />`}
      >
        <div style={{ display: "flex", gap: 8 }}>
          <PV_RiskPill level="low" />
          <PV_RiskPill level="medium" />
          <PV_RiskPill level="high" />
        </div>
      </V4Spec>

      <V4Spec
        id="atom-copyablecode"
        tier="new"
        name="CopyableCode"
        level="atom"
        summary="`<code>` inline copiável. Mono 11px, cursor-pointer, ícone copy 10px à direita. Title attr explica o efeito. Útil para trace IDs, hashes, IDs internos."
        summaryEn="Inline copyable <code>. Mono 11px, cursor-pointer, copy icon. Useful for trace IDs, hashes, internal IDs."
        props={[
          { name: "children", type: "string", desc: "Conteúdo a copiar" },
          { name: "tip", type: "string", desc: "Title attr · explica o que vai ser copiado", default: "\"copiar\"" },
        ]}
        when={[
          "trace_id no ModelingDiagnosticsModal",
          "Session ID em painéis de debug",
          "Hash de arquivo em DuplicateFileModal",
          "NÃO usar para code blocks — só inline curto (<32 chars)",
        ]}
        refs={[
          "web/src/features/modeling-3d/components/ModelingDiagnosticsModal.tsx · trace_id span",
        ]}
        a11y={[
          "role=\"button\" + tabIndex={0} (é interativo)",
          "Enter / Space copiam",
          "aria-label=\"Copiar {tip}\" para clareza",
          "Toast/inline confirmação após copy (não pode ser silencioso)",
        ]}
        code={`<CopyableCode tip="copiar trace_id">
  {traceId}
</CopyableCode>`}
      >
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <PV_CopyableCode>tr_8a4f9c12d</PV_CopyableCode>
          <PV_CopyableCode>sha256:e7b9…</PV_CopyableCode>
          <PV_CopyableCode>agent_judite</PV_CopyableCode>
        </div>
      </V4Spec>
    </DocSection>
  );
}

Object.assign(window, { V4_AtomsSection, PV_Textarea, PV_Select, PV_NumberInput, PV_ProgressBar, PV_HelperIcon, PV_RiskPill, PV_CopyableCode });
