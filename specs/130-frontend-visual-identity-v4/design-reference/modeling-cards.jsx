// 3D modeling cards — ModelingPlanCard, ModelingEditCard, ModelingDiagnosticsModal

function ModelingPlanCard({ status = "waiting_approval", showRejectForm = false }) {
  const STATUS = {
    waiting_approval: { label: "aguardando aprovação", tone: "ember" },
    running: { label: "executando", tone: "amethyst" },
    completed: { label: "concluído", tone: "ok" },
    failed: { label: "falhou", tone: "err" },
  };
  const s = STATUS[status];
  const steps = [
    { idx: 1, name: "Criar coleção 'rag-scene'", risk: "low" },
    { idx: 2, name: "Importar mesh do servidor postgres.fbx", risk: "low" },
    { idx: 3, name: "Aplicar material âmbar emissivo (intensidade 4.2)", risk: "medium" },
    { idx: 4, name: "Excluir objetos default (Cube, Camera, Light)", risk: "high", approval: true },
    { idx: 5, name: "Configurar render: Cycles · 256 samples · 1080p", risk: "medium" },
    { idx: 6, name: "Iniciar render e exportar PNG", risk: "low" },
  ];
  const hasHighRisk = steps.some((st) => st.risk === "high");

  return (
    <div
      style={{
        width: 560,
        padding: "16px 18px",
        background: "color-mix(in srgb, var(--amethyst) 4%, var(--bg-card))",
        border: "1px solid color-mix(in srgb, var(--amethyst) 28%, transparent)",
        borderRadius: "var(--radius)",
        boxShadow: "0 12px 32px -20px var(--amethyst-glow)",
        fontFamily: "var(--font-text)",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 12 }}>
        <div style={{ width: 36, height: 36, borderRadius: 10, background: "linear-gradient(155deg, var(--amethyst), color-mix(in srgb, var(--amethyst) 40%, var(--bg-ink)))", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", flexShrink: 0 }}>
          <Icon name="boxes" size={16} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontFamily: "var(--font-display)", fontSize: 15, color: "var(--text)", letterSpacing: "0.02em", textTransform: "uppercase" }}>
              Plano 3D · MCP
            </span>
            <Tag tone={s.tone}>{s.label}</Tag>
            <Tag tone="amethyst">Blender 4.2</Tag>
            <Tag tone="neutral">planner: IA</Tag>
          </div>
          <p style={{ margin: "8px 0 0", fontSize: 12.5, color: "var(--text-soft)", lineHeight: 1.55 }}>
            Cena com server postgres em destaque, atmosfera de fragua quente. 6 passos, 1 alto risco (deletar defaults).
          </p>
        </div>
      </div>

      {/* High-risk warning */}
      {hasHighRisk && status === "waiting_approval" && (
        <div style={{ display: "flex", gap: 10, padding: "10px 12px", borderRadius: 8, background: "color-mix(in srgb, var(--err) 8%, transparent)", border: "1px solid color-mix(in srgb, var(--err) 25%, transparent)", marginBottom: 12 }}>
          <Icon name="shield" size={14} stroke="var(--err)" />
          <div style={{ flex: 1, fontSize: 12, color: "var(--text-soft)", lineHeight: 1.5 }}>
            <strong style={{ color: "var(--err)" }}>1 passo alto risco</strong> — exclusão de objetos default. Revise antes de aprovar.
          </div>
        </div>
      )}

      {/* Steps */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 12 }}>
        {steps.map((st) => (
          <PlanStep key={st.idx} {...st} active={status === "running" && st.idx === 3} done={status === "running" && st.idx < 3} />
        ))}
      </div>

      {/* Footer / actions */}
      {status === "waiting_approval" && !showRejectForm && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, paddingTop: 12, borderTop: "1px solid var(--line-soft)" }}>
          <Mono size={10} color="var(--faint)" style={{ marginRight: "auto" }}>
            6 passos · ~2 min de execução
          </Mono>
          <ModalButton tone="ghost" label="Rejeitar" />
          <ModalButton tone="amethyst" icon="check" label="Aprovar e executar" />
        </div>
      )}
      {status === "running" && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, paddingTop: 12, borderTop: "1px solid var(--line-soft)" }}>
          <div style={{ display: "flex", gap: 3 }}>
            <Dot delay={0} />
            <Dot delay={0.2} />
            <Dot delay={0.4} />
          </div>
          <Mono size={11} color="var(--amethyst)">
            executando passo 3 / 6 · 00:42
          </Mono>
          <span style={{ flex: 1 }} />
          <ModalButton tone="ghost" label="Cancelar" />
        </div>
      )}
      {status === "failed" && (
        <div>
          <div style={{ padding: "10px 12px", borderRadius: 8, background: "color-mix(in srgb, var(--err) 8%, transparent)", border: "1px solid color-mix(in srgb, var(--err) 25%, transparent)", marginBottom: 12 }}>
            <Mono size={10} color="var(--err)" style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>erro · passo 4</Mono>
            <div style={{ marginTop: 4, fontSize: 12, color: "var(--text-soft)", lineHeight: 1.5 }}>
              Blender retornou: <span style={{ fontFamily: "var(--font-mono)", color: "var(--text)" }}>Object "Cube" not found in scene "rag-scene"</span>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <ModalButton tone="ghost" icon="x" label="Revisar plano" />
            <ModalButton tone="amethyst" label="Tentar novamente" />
          </div>
        </div>
      )}
    </div>
  );
}

function PlanStep({ idx, name, risk, approval, active, done }) {
  const riskColor = risk === "high" ? "var(--err)" : risk === "medium" ? "var(--ember)" : "var(--ok)";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "8px 10px",
        borderRadius: 6,
        background: active ? "color-mix(in srgb, var(--amethyst) 8%, transparent)" : "transparent",
        opacity: done ? 0.5 : 1,
      }}
    >
      <span style={{ width: 18, textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 10, color: done ? "var(--ok)" : "var(--faint)" }}>
        {done ? "✓" : String(idx).padStart(2, "0")}
      </span>
      <span style={{ flex: 1, fontSize: 12.5, color: "var(--text)" }}>{name}</span>
      {approval && (
        <Mono size={9.5} color="var(--err)" style={{ textTransform: "uppercase", letterSpacing: "0.1em" }}>
          requer aprovação
        </Mono>
      )}
      <span style={{ width: 6, height: 6, borderRadius: 999, background: riskColor, boxShadow: risk === "high" ? "0 0 6px color-mix(in srgb, var(--err) 60%, transparent)" : "none" }} />
    </div>
  );
}

// Modeling Edit Card — applied after plan completes, allows tweaks
function ModelingEditCard() {
  return (
    <div
      style={{
        width: 480,
        padding: "16px 18px",
        background: "color-mix(in srgb, var(--ember) 4%, var(--bg-card))",
        border: "1px solid color-mix(in srgb, var(--ember) 28%, transparent)",
        borderRadius: "var(--radius)",
        fontFamily: "var(--font-text)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <Icon name="sparkles" size={14} stroke="var(--ember)" />
        <span style={{ fontFamily: "var(--font-display)", fontSize: 14, color: "var(--text)", letterSpacing: "0.02em", textTransform: "uppercase" }}>
          Edição · iteração rápida
        </span>
        <span style={{ flex: 1 }} />
        <Tag tone="ok">cena ativa</Tag>
      </div>

      <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--text-soft)", lineHeight: 1.55 }}>
        Cena rendereada às 14:42. Quer ajustar algo? Descreva e JUDITE manda só o delta pra Blender — sem refazer tudo.
      </p>

      <div style={{ background: "var(--bg-ink)", border: "1px solid var(--line)", borderRadius: 10, padding: "10px 12px", marginBottom: 12 }}>
        <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.12em", marginBottom: 6, display: "block" }}>
          última edição
        </Mono>
        <div style={{ fontSize: 12.5, color: "var(--text)", fontFamily: "var(--font-mono)" }}>
          material.emission.intensity: <span style={{ color: "var(--muted)" }}>2.0</span> → <span style={{ color: "var(--ember)" }}>4.2</span>
        </div>
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <PromptChip label="mais quente" />
        <PromptChip label="adicionar névoa" />
        <PromptChip label="câmera mais baixa" />
        <PromptChip label="dobrar samples" />
      </div>
    </div>
  );
}

function PromptChip({ label }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", height: 26, padding: "0 10px", borderRadius: 999, background: "var(--bg-card)", border: "1px solid var(--line-soft)", fontSize: 11.5, color: "var(--text-soft)" }}>
      {label}
    </span>
  );
}

// Diagnostics modal — read-only inspection of plan execution
function ModelingDiagnosticsCard() {
  return (
    <div
      style={{
        width: 540,
        padding: "18px 20px",
        background: "var(--bg-elev)",
        border: "1px solid var(--line)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "0 16px 36px -20px var(--amethyst-glow)",
        fontFamily: "var(--font-text)",
      }}
    >
      <div style={{ marginBottom: 16 }}>
        <Mono size={10} color="var(--amethyst)" style={{ textTransform: "uppercase", letterSpacing: "0.14em" }}>
          DIAGNÓSTICO · PLAN 4F7
        </Mono>
        <h3 style={{ margin: "8px 0 0", fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 400, letterSpacing: "0.015em", textTransform: "uppercase", color: "var(--text)" }}>
          Linha do tempo da execução
        </h3>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8, marginBottom: 16 }}>
        <DiagStat label="duração" value="1m 42s" />
        <DiagStat label="passos" value="6/6" />
        <DiagStat label="confiança" value="92%" tone="ok" />
        <DiagStat label="risco" value="baixo" tone="ok" />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {[
          { time: "14:42:02", event: "plan.received", source: "JUDITE", color: "var(--ember)" },
          { time: "14:42:03", event: "plan.approved", source: "user", color: "var(--ok)" },
          { time: "14:42:04", event: "blender.connect", source: "MCP", color: "var(--amethyst)" },
          { time: "14:42:18", event: "step.3 · warn", source: "blender", color: "var(--ember)", detail: "material substituído (fallback BSDF)" },
          { time: "14:43:44", event: "plan.completed", source: "JUDITE", color: "var(--ok)" },
        ].map((e, i) => (
          <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "6px 0" }}>
            <Mono size={10} color="var(--faint)" style={{ minWidth: 64 }}>
              {e.time}
            </Mono>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: e.color, marginTop: 6, flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <Mono size={11.5} color="var(--text)">
                {e.event}
              </Mono>
              <Mono size={9.5} color="var(--muted)" style={{ marginLeft: 8 }}>
                · {e.source}
              </Mono>
              {e.detail && (
                <div style={{ marginTop: 2, fontSize: 11, color: "var(--muted)" }}>{e.detail}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DiagStat({ label, value, tone }) {
  const color = tone === "ok" ? "var(--ok)" : tone === "err" ? "var(--err)" : "var(--text)";
  return (
    <div style={{ padding: "10px 12px", borderRadius: 8, background: "var(--bg-card)", border: "1px solid var(--line-soft)" }}>
      <Mono size={9.5} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>
        {label}
      </Mono>
      <div style={{ marginTop: 4, fontSize: 15, color, fontFamily: "var(--font-display)", letterSpacing: "0.005em" }}>{value}</div>
    </div>
  );
}

Object.assign(window, { ModelingPlanCard, ModelingEditCard, ModelingDiagnosticsCard, PlanStep, PromptChip });
