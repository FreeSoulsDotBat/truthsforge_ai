# Mapa da aplicacao

## Monorepo

O projeto e um monorepo: backend, frontends, documentacao, pacotes compartilhados e infra vivem no mesmo repositorio.

- `backend`: API, regras de negocio, providers LLM, storage, RAG, agentes, workers locais e modelagem 3D.
- `apps/web`: interface principal em React.
- `apps/docs`: documentacao Docusaurus que le a pasta `docs`.
- `apps/desktop`: wrapper Tauri para desktop.
- `apps/mobile`: wrapper Capacitor para Android.
- `packages/types`: espaco reservado para tipos compartilhados.
- `packages/ui`: espaco reservado para componentes compartilhados.
- `infra`: Docker Compose e configuracao dos servicos locais.
- `docs`: documentacao do produto, arquitetura e operacao.
- `specs`: especificacoes SDD vivas (padrao GitHub Spec Kit, pastas `NNN-<slug>`); `specs/000-repo-foundation` e o baseline; specs absorvidas ficam congeladas em `specs/_legacy`.
- `.specify`: constituicao (`memory/constitution.md`), templates e scripts do Spec Kit.
- `.agents/skills`: procedimentos versionados por bounded context para Codex, Claude Code, Devin e humanos.
- `.claude/skills/speckit-*`: fases SDD (constitution/specify/clarify/plan/analyze/tasks/implement) para Claude Code.
- `.local`: dados locais ignorados pelo Git.

## Backend

O backend e uma aplicacao FastAPI. Ele expoe rotas REST e streaming SSE para o chat.

- `api`: roteadores HTTP.
- `core`: configuracoes e contratos centrais.
- `llm_gateway`: camada que conversa com OpenAI, Anthropic e Google.
- `judite`: persona/orquestracao inicial da JUDITE.
- `agents`: pacote reservado para runtime agentico (LangGraph/LangChain), ainda stub; a selecao multiagente vive hoje em `api/routes/chat.py`.
- `rag`: embeddings locais, VectorStore, Qdrant, filtros e fallback por metadados.
- `files`: biblioteca de arquivos, upload/download, deduplicacao, parsing e OCR opcional.
- `prompts`: biblioteca e renderizacao de prompts.
- `tools`: catalogo, avaliacao de permissao e runtime seguro inicial de ferramentas internas.
- `security`: segredos e permissoes.
- `audit`: eventos de auditoria.
- `cost_governor`: orcamento, estimativa de custo e uso mensal.
- `storage`: persistencia em Postgres com fallback JSON.
- `workers`: filas para importacao do ChatGPT e indexacao de arquivos (em memoria por padrao; Redis/Valkey opt-in via `TRUTHS_FORGE_QUEUE_BACKEND`), com recuperacao de pendencias.
- `importers`: parsing e jobs da importacao do ChatGPT (export → sessoes/mensagens).
- `chat`: helpers de sessao de chat (ex.: limpeza de sessoes vazias).
- `modeling`: bounded context chat-first de modelagem 3D via MCP local — orchestrator de chat, planner LLM + heuristico, loop agentico de auto-correcao, verificacao geometrica/visual, politica, observabilidade/trace e adapters (Blender headless, Fusion MCP oficial, MCP standalone) com fallback mock.

## Frontend web

O frontend React e a primeira experiencia do usuario.

- Sidebar esquerda: sessoes (com `ChatModeling3DBadge` para chats 3D), historico paginado, projetos/pastas e novo chat. Todo chat exige titulo nao vazio antes da primeira mensagem (ADR-014): o frontend abre `ChatTitleRequiredDialog`, envia `title` em `POST /api/chat/stream` e o backend valida com HTTP 422 quando `TRUTHS_FORGE_REQUIRE_CHAT_TITLE` esta ativa.
- Centro: chat com streaming, anexos, MCP 3D ativado por chat (ADR-013) e upload rapido. Chats 3D mostram `ModelingPlanCard` (aprovacao por botoes inline em `apps/web/src/features/modeling-3d/components/`, com banner para etapas high-risk e estados `executing`/`completed`/`failed` com retry+revise) e `ModelingEditCard` (mini-planos auto-aprovados). Anexos (imagem ou arquivo 3D) disparam a analise profunda (`POST /api/chat/sessions/{id}/attachments/analyze`) apos o envio. Botao de diagnostico no cabecalho abre `ModelingDiagnosticsModal` read-only.
- Painel direito: contexto, custos, RAG, auditoria, prompts, configuracao, arquivos, bases, projetos e agentes. O painel 3D no dashboard foi removido com ADR-013; toda interacao 3D ocorre no chat.
- Configuracoes: API keys por provedor, registry editavel de modelos e secao "Modelagem 3D" (Blender path, Fusion MCP URL, transport, timeouts, status de adapters).
- Arquivos: biblioteca bruta de arquivos enviados, recebidos, gerados ou importados, com paginacao, filtros, preview/download e status de indexacao.
- Bases: colecoes curadas de documentos indexados para RAG.
- Projetos: organizacao de chats e pastas, com bases atreladas quando fizer sentido.

## Documentacao

`apps/docs` roda Docusaurus em `http://127.0.0.1:3000`.

Ele nao duplica a documentacao: le diretamente os arquivos Markdown da pasta `docs/` do monorepo (`path: "../../docs"` no Docusaurus).

## SDD

O SDD segue o padrão **GitHub Spec Kit**. Invariantes em `.specify/memory/constitution.md`; templates em `.specify/templates/`; fases como skills em `.claude/skills/speckit-*`. As specs vivem em `specs/NNN-<slug>/` e organizam intenção, plano, tasks e handoff sem substituir `docs/`.

- `.specify/memory/constitution.md`: princípios não-negociáveis (P1–P9) que governam todas as fases.
- `AGENTS.md`: contrato comum de arquitetura, prioridade de contexto e qualidade.
- `CLAUDE.md`: adaptador mínimo para Claude Code carregar `AGENTS.md`.
- `specs/000-repo-foundation/spec.md`: baseline do MVP local-first.
- `specs/000-repo-foundation/plan.md`: plano técnico e sequência de workstreams.
- `specs/000-repo-foundation/tasks.md`: backlog rastreável por prioridade e executor sugerido.
- `specs/000-repo-foundation/handoff.md`: continuidade quando humanos, Codex, Claude Code ou Devin alternarem a execução.
- `specs/NNN-<slug>/`: specs por domínio (chat, gateway, files/RAG, import/workers, agents/tools, cost/audit, storage, prompts, frontend, mobile/desktop, 3D, artifacts) — catálogo em `specs/README.md`.
- `specs/_legacy/`: specs absorvidas por um domínio novo, congeladas.
- `.claude/skills/speckit-*`: fases do fluxo SDD para Claude Code.
- `docs/delivery-checklist.md`: checklist obrigatório de entrega para PRs e handoffs.
- `.agents/skills/`: skills instruction-first para mapear repo, validar qualidade e trabalhar nos principais bounded contexts.

## Dados

- Postgres guarda estado transacional em tabelas JSONB: chats, mensagens, modelos, agentes, prompts, projetos, pastas, documentos, arquivos, bases, importacoes, auditoria, politica de custo e modelagem 3D.
- Qdrant guarda vetores dos documentos indexados.
- Valkey/Redis serve cache/fila; os workers de importacao/indexacao rodam em memoria por padrao e podem usar Redis/Valkey via `TRUTHS_FORGE_QUEUE_BACKEND=redis|valkey`.
- `.local/files` guarda documentos locais.
- `.local/state` guarda segredos cifrados, estado local auxiliar e o discovery default do bridge Fusion quando o backend usa `settings.state_dir`.
- `.local/imports` guarda uploads de exportacao do ChatGPT.
- `.local/modeling` guarda workspaces, snapshots e artefatos 3D gerados.

## Fluxo de chat

1. Usuario cria chat e opcionalmente marca como 3D.
2. Antes da primeira mensagem, o React exige um titulo nao vazio e nao-default via `ChatTitleRequiredDialog`.
3. Frontend chama `POST /api/chat/stream` com `title`. Backend rejeita com 422 se o titulo estiver ausente ou ainda for `Novo chat`/`New chat`.
4. Backend resolve agente principal, agente solicitado, agentes de apoio e bases atreladas.
5. Se `chat.is_modeling_3d=true`, o agente segue a state machine `discovery → planning → approved → executing → editing` (com `failed` distinto numa execução que quebra — DT-008) (ADR-013). As transições são dirigidas por capacidades do `ModelingChatOrchestrator` (agente de descoberta, propor plano, propor edição, análise de anexo) — não por tools registradas na allowlist.
6. Caso contrário, backend escolhe o modelo pelo Model Registry.
7. Cost Governor estima custo antes da chamada.
8. LLM Gateway chama o provedor real ou fallback dev. Modos especiais (Deep Research, imagem, resumo oficial) seguem mutuamente exclusivos com chat 3D.
9. Imagens geradas, anexos e exports 3D viram `PlatformFile` em `Arquivos` e podem ser indexados.
10. Backend envia tokens via SSE; o evento `modeling_plan` (com o plano, incluindo edições via `kind=edit`, e o `trace_id`) leva o estado 3D para a UI.
11. Mensagens, metadados e auditoria sao salvos no store.

## Fluxo de RAG

1. Arquivos entram pela biblioteca `Arquivos`, por upload, importacao ou geracao.
2. O backend extrai texto/metadados e indexa chunks no Qdrant.
3. O usuario organiza documentos em `Bases de conhecimento`.
4. Projetos e agentes podem referenciar bases.
5. No chat, o backend busca apenas nas bases ativas para aquele agente/projeto.
6. O Qdrant ranqueia semanticamente os chunks e o backend aplica regras de escopo, prioridade e limite antes de montar o prompt.
