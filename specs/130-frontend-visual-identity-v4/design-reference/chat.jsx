// Main column — chat messages, composer, empty state

function ChatHeader({ theme, title, subtitle, meta = [] }) {
  return (
    <div style={{ padding: "26px 40px 22px", borderBottom: "1px solid var(--line-soft)" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 20 }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
            <Mono size={10} color="var(--faint)">
              {meta[0] || "CONVERSA"}
            </Mono>
            <span style={{ width: 3, height: 3, borderRadius: 999, background: "var(--faint)" }} />
            <Mono size={10} color="var(--faint)">
              {meta[1] || "12:42"}
            </Mono>
          </div>
          <h1
            style={{
              margin: 0,
              fontFamily: "var(--font-display)",
              fontSize: 26,
              fontWeight: 400,
              letterSpacing: "0.01em",
              textTransform: "uppercase",
              color: "var(--text)",
              lineHeight: 1.05,
            }}
          >
            {title}
          </h1>
          {subtitle && (
            <div style={{ marginTop: 10, fontSize: 13, color: "var(--muted)", lineHeight: 1.55, maxWidth: 640 }}>{subtitle}</div>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
          <Tag tone="neutral">
            <Icon name="folder" size={10} />
            Forja pessoal
          </Tag>
          <Tag tone="ember">
            <Pulse color="var(--ember)" size={4} />
            JUDITE
          </Tag>
          <div style={{ width: 28, height: 28, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted)" }}>
            <Icon name="more-horizontal" size={16} />
          </div>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ role, time, body, theme, reasoning, attachments }) {
  const isUser = role === "user";
  return (
    <div style={{ display: "flex", gap: 14, padding: "14px 0" }}>
      {isUser ? (
        <Avatar kind="user" size={28} />
      ) : (
        <Avatar kind="judite" size={28} theme={theme} />
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <span style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text)" }}>
            {isUser ? "Você" : "JUDITE"}
          </span>
          <Mono size={10} color="var(--faint)">
            {time}
          </Mono>
          {!isUser && (
            <>
              <span style={{ width: 2, height: 2, borderRadius: 999, background: "var(--faint)" }} />
              <Mono size={10} color="var(--faint)">
                gpt-4o · 1.2s · 480 tok
              </Mono>
            </>
          )}
        </div>
        {reasoning && <ReasoningStrip {...reasoning} theme={theme} />}
        <div style={{ fontSize: 14, lineHeight: 1.7, color: isUser ? "var(--text-soft)" : "var(--text)", maxWidth: 720 }}>{body}</div>
        {attachments && <AttachmentRow items={attachments} />}
      </div>
    </div>
  );
}

function ReasoningStrip({ steps = [], duration, collapsed = true, theme }) {
  return (
    <div
      style={{
        marginBottom: 12,
        marginTop: 2,
        padding: "10px 12px",
        background: "var(--bg-card)",
        borderRadius: "var(--radius-sm)",
        border: "1px solid var(--line-soft)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: collapsed ? 0 : 10 }}>
        <Icon name="brain" size={13} stroke="var(--ember)" />
        <Mono size={10.5} color="var(--text-soft)" style={{ textTransform: "uppercase", letterSpacing: "0.08em" }}>
          Trilha de raciocínio
        </Mono>
        <span style={{ flex: 1 }} />
        <Mono size={10} color="var(--faint)">
          {duration || "4.2s · 6 etapas"}
        </Mono>
        <Icon name={collapsed ? "chevron-right" : "chevron-down"} size={12} stroke="var(--faint)" />
      </div>
      {!collapsed && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, paddingLeft: 4 }}>
          {steps.map((s, i) => (
            <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 10, position: "relative" }}>
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 999,
                  background: i === steps.length - 1 ? "var(--ember)" : "var(--muted)",
                  marginTop: 6,
                  flexShrink: 0,
                  boxShadow: i === steps.length - 1 ? "0 0 8px var(--ember-glow)" : "none",
                }}
              />
              <div style={{ fontSize: 12, color: i === steps.length - 1 ? "var(--text)" : "var(--muted)" }}>{s}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AttachmentRow({ items = [] }) {
  return (
    <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 6 }}>
      {items.map((it, i) => (
        <div
          key={i}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 10px",
            borderRadius: 8,
            background: "var(--bg-card)",
            border: "1px solid var(--line-soft)",
            color: "var(--text-soft)",
            fontSize: 12,
          }}
        >
          <Icon name={it.icon || "file-text"} size={12} stroke="var(--muted)" />
          <span>{it.name}</span>
          <Mono size={9.5} color="var(--faint)">
            {it.size}
          </Mono>
        </div>
      ))}
    </div>
  );
}

function CodeBlock({ lang = "sql", lines }) {
  return (
    <div
      style={{
        marginTop: 12,
        marginBottom: 4,
        background: "var(--bg-ink)",
        border: "1px solid var(--line-soft)",
        borderRadius: "var(--radius-sm)",
        overflow: "hidden",
        maxWidth: 720,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", borderBottom: "1px solid var(--line-soft)" }}>
        <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.1em" }}>
          {lang}
        </Mono>
        <Mono size={10} color="var(--faint)">
          copiar
        </Mono>
      </div>
      <div style={{ padding: "10px 14px", fontFamily: "var(--font-mono)", fontSize: 12, lineHeight: 1.7, color: "var(--text-soft)" }}>
        {lines.map((l, i) => (
          <div key={i} style={{ display: "flex", gap: 14 }}>
            <span style={{ color: "var(--faint)", width: 16, textAlign: "right", flexShrink: 0 }}>{i + 1}</span>
            <span dangerouslySetInnerHTML={{ __html: l }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function Composer({ theme, value = "" }) {
  return (
    <div style={{ padding: "16px 40px 24px" }}>
      <div style={{ maxWidth: 820, margin: "0 auto" }}>
        {/* Context strip */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, paddingLeft: 4, flexWrap: "wrap" }}>
          <Chip label="Agente" value="JUDITE" dot dotColor="var(--ember)" />
          <Chip label="Projeto" value="Forja pessoal" />
          <Chip label="Bases" value="2 ativas" />
          <span style={{ flex: 1 }} />
          <Mono size={10} color="var(--faint)">
            modo · padrão
          </Mono>
        </div>

        {/* Input pill */}
        <div
          style={{
            background: "var(--bg-card)",
            border: "1px solid var(--line)",
            borderRadius: "var(--radius-lg)",
            padding: "14px 16px",
            boxShadow: "var(--shadow-soft)",
            position: "relative",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: 12, minHeight: 60 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14, color: value ? "var(--text)" : "var(--muted)", lineHeight: 1.6 }}>
                {value || "Mensagem para JUDITE..."}
              </div>
              {value && (
                <div style={{ marginTop: 2, fontSize: 14, color: "var(--text)", lineHeight: 1.6 }}>
                  <span style={{ display: "inline-block", width: 1.5, height: 17, background: "var(--ember)", verticalAlign: "text-bottom", animation: "tfBlink 1s infinite" }} />
                </div>
              )}
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--line-soft)" }}>
            <ComposerAction icon="paperclip" />
            <ComposerAction icon="plus" label="Modo" />
            <ComposerAction icon="image" />
            <ComposerAction icon="mic" />
            <span style={{ flex: 1 }} />
            <Mono size={10} color="var(--faint)">
              <KBD>⌘</KBD> <KBD>↵</KBD> enviar
            </Mono>
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: 999,
                background: value ? "var(--ember)" : "var(--bg-chip)",
                color: value ? "var(--ember-ink)" : "var(--faint)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginLeft: 4,
                boxShadow: value ? "0 8px 24px -10px var(--ember-glow)" : "none",
              }}
            >
              <Icon name="arrow-up" size={16} strokeWidth={2} />
            </div>
          </div>
        </div>

        {/* Footer hint */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, marginTop: 12 }}>
          <Mono size={10} color="var(--faint)">
            local · llm próprio · postgres+qdrant
          </Mono>
        </div>
      </div>
    </div>
  );
}

function ComposerAction({ icon, label }) {
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        height: 30,
        padding: label ? "0 10px" : "0 8px",
        borderRadius: 8,
        color: "var(--muted)",
        fontSize: 12,
      }}
    >
      <Icon name={icon} size={14} />
      {label && <span>{label}</span>}
    </div>
  );
}

// Main chat area showing a populated conversation
function ChatMain({ theme }) {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, background: "var(--bg)" }}>
      <ChatHeader
        theme={theme}
        title="Pipeline RAG no Postgres com pgvector"
        subtitle="Vamos passar do esquema atual para uma indexação semântica resiliente. Documentos, chunks, embeddings e auditoria de tokens — tudo no mesmo banco."
        meta={["FORJA PESSOAL · CONVERSA", "iniciada às 12:42"]}
      />

      <div style={{ flex: 1, overflow: "hidden", padding: "12px 40px 0" }}>
        <div style={{ maxWidth: 820, margin: "0 auto", display: "flex", flexDirection: "column" }}>
          <MessageBubble
            role="user"
            time="12:42"
            theme={theme}
            body={
              <>
                Bora montar o pipeline RAG no nosso Postgres. Já temos a tabela <code style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, padding: "1px 5px", borderRadius: 4, background: "var(--bg-card)", color: "var(--ember)" }}>documents</code>, mas falta cravar o pedaço dos embeddings e o trecho de auditoria. Bom partir do quê?
              </>
            }
            attachments={[
              { icon: "file-text", name: "schema.sql", size: "12 KB" },
              { icon: "image", name: "diagrama-rag.png", size: "287 KB" },
            ]}
          />

          <MessageBubble
            role="assistant"
            time="12:42"
            theme={theme}
            reasoning={{ duration: "4.2s · 6 etapas", collapsed: true }}
            body={
              <>
                <p style={{ margin: "0 0 10px" }}>
                  Boa — três partes pra deixar de pé hoje: <strong style={{ color: "var(--text)" }}>extensão</strong>, <strong style={{ color: "var(--text)" }}>schema</strong> e <strong style={{ color: "var(--text)" }}>política de chunking</strong>. Começo pelo Postgres nu:
                </p>
                <CodeBlock
                  lang="sql · postgres"
                  lines={[
                    '<span style="color:var(--ember)">CREATE EXTENSION</span> <span style="color:var(--text)">IF NOT EXISTS</span> vector;',
                    '',
                    '<span style="color:var(--ember)">CREATE TABLE</span> <span style="color:var(--text)">document_chunks</span> (',
                    '  id          uuid <span style="color:var(--muted)">primary key default</span> gen_random_uuid(),',
                    '  document_id uuid <span style="color:var(--muted)">references</span> documents(id) <span style="color:var(--muted)">on delete cascade</span>,',
                    '  chunk_index int  <span style="color:var(--muted)">not null</span>,',
                    '  embedding   <span style="color:var(--ember)">vector(1536)</span>,',
                    '  content     text <span style="color:var(--muted)">not null</span>,',
                    '  tokens      int',
                    ');',
                  ]}
                />
                <p style={{ margin: "12px 0 0" }}>
                  Próximo passo: índice HNSW e a função de busca híbrida (BM25 + vetor). Quer que eu já gere a migração ou prefere validarmos o tamanho de chunk antes?
                </p>
              </>
            }
          />
        </div>
      </div>

      <Composer theme={theme} />
    </div>
  );
}

// Empty state — typographic hero, calmer
function ChatEmpty({ theme }) {
  const actions = [
    { icon: "flame", label: "O que vamos forjar hoje?", hint: "abrir conversa livre" },
    { icon: "boxes", label: "Auditar custos do mês", hint: "OpenAI · Anthropic · local" },
    { icon: "brain", label: "Estudar um tópico a fundo", hint: "pesquisa profunda · 2-8 min" },
    { icon: "image", label: "Gerar imagem", hint: "diagramas, capas, esboços" },
  ];
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, background: "var(--bg)" }}>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "40px" }}>
        <div style={{ maxWidth: 720, width: "100%" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, marginBottom: 22 }}>
            <span style={{ width: 32, height: 1, background: "var(--line)" }} />
            <Mono size={10} color="var(--faint)" style={{ textTransform: "uppercase", letterSpacing: "0.2em" }}>
              terça · 20 maio · 14:08
            </Mono>
            <span style={{ width: 32, height: 1, background: "var(--line)" }} />
          </div>
          <h1
            style={{
              margin: 0,
              textAlign: "center",
              fontFamily: "var(--font-display)",
              fontSize: 52,
              fontWeight: 400,
              letterSpacing: "0.005em",
              textTransform: "uppercase",
              lineHeight: 1.0,
              color: "var(--text)",
            }}
          >
            Onde se descansa,<br />
            <span
              style={{
                fontFamily: "var(--font-serif)",
                fontStyle: "italic",
                textTransform: "lowercase",
                fontWeight: 400,
                letterSpacing: "-0.01em",
                color: "var(--ember)",
              }}
            >
              forja-se
            </span>{" "}
            a verdade.
          </h1>
          <p style={{ textAlign: "center", margin: "18px auto 0", maxWidth: 480, fontSize: 14, color: "var(--muted)", lineHeight: 1.6 }}>
            Bom dia, Ricardo. JUDITE leu as 3 notas que você anexou ontem e está pronta. Escolha um ponto de partida ou escreva direto.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 36 }}>
            {actions.map((a, i) => (
              <div
                key={i}
                style={{
                  padding: "14px 16px",
                  borderRadius: "var(--radius)",
                  background: "var(--bg-card)",
                  border: "1px solid var(--line-soft)",
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                }}
              >
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 10,
                    background: "color-mix(in oklch, var(--ember) 10%, var(--bg-ink))",
                    color: "var(--ember)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    border: "1px solid color-mix(in oklch, var(--ember) 20%, transparent)",
                    flexShrink: 0,
                  }}
                >
                  <Icon name={a.icon} size={16} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, color: "var(--text)", fontWeight: 500 }}>{a.label}</div>
                  <Mono size={10} color="var(--faint)" style={{ marginTop: 2, display: "block" }}>
                    {a.hint}
                  </Mono>
                </div>
                <Icon name="arrow-up-right" size={14} stroke="var(--faint)" />
              </div>
            ))}
          </div>

          <div style={{ marginTop: 32, display: "flex", alignItems: "center", justifyContent: "center", gap: 14 }}>
            <Mono size={10} color="var(--faint)">
              3 chats abertos
            </Mono>
            <span style={{ width: 2, height: 2, borderRadius: 999, background: "var(--faint)" }} />
            <Mono size={10} color="var(--faint)">
              R$ 12,84 gastos em maio
            </Mono>
            <span style={{ width: 2, height: 2, borderRadius: 999, background: "var(--faint)" }} />
            <Mono size={10} color="var(--faint)">
              48 documentos indexados
            </Mono>
          </div>
        </div>
      </div>

      <Composer theme={theme} />
    </div>
  );
}

Object.assign(window, { ChatMain, ChatEmpty, Composer, MessageBubble });
