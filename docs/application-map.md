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
- `specs`: especificacoes SDD vivas; `specs/repo-foundation` e o baseline compartilhado por humanos e agentes.
- `.agents/skills`: procedimentos versionados por bounded context para Codex, Claude Code, Devin e humanos.
- `.local`: dados locais ignorados pelo Git.

## Backend

O backend e uma aplicacao FastAPI. Ele expoe rotas REST e streaming SSE para o chat.

- `api`: roteadores HTTP.
- `core`: configuracoes e contratos centrais.
- `llm_gateway`: camada que conversa com OpenAI, Anthropic e Google.
- `judite`: persona/orquestracao inicial da JUDITE.
- `agents`: runtime inicial com LangGraph/LangChain quando disponivel, selecao multiagente e politicas.
- `rag`: embeddings locais, VectorStore, Qdrant, filtros e fallback por metadados.
- `files`: biblioteca de arquivos, upload/download, deduplicacao, parsing e OCR opcional.
- `prompts`: biblioteca e renderizacao de prompts.
- `tools`: catalogo, avaliacao de permissao e runtime seguro inicial de ferramentas internas.
- `security`: segredos e permissoes.
- `audit`: eventos de auditoria.
- `cost_governor`: orcamento, estimativa de custo e uso mensal.
- `storage`: persistencia em Postgres com fallback JSON.
- `workers`: filas em memoria para importacao do ChatGPT e indexacao de arquivos, com recuperacao de pendencias.
- `modeling`: bounded context de modelagem 3D via MCP local, com planner, politica, adapters e execução segura do Blender quando disponível.

## Frontend web

O frontend React e a primeira experiencia do usuario.

- Sidebar esquerda: sessoes (com `ChatModeling3DBadge` para chats 3D), historico paginado, projetos/pastas e novo chat. Todo chat exige titulo nao vazio antes da primeira mensagem (ADR-014).
- Centro: chat com streaming, anexos, MCP 3D ativado por chat (ADR-013) e upload rapido. Chats 3D mostram `ModelingPlanCard` (aprovacao por botoes inline) e `ModelingEditCard` (mini-planos executados). Botao de diagnostico no cabecalho abre `ModelingDiagnosticsModal` read-only.
- Painel direito: contexto, custos, RAG, auditoria, prompts, configuracao, arquivos, bases, projetos e agentes. O painel 3D no dashboard foi removido com ADR-013; toda interacao 3D ocorre no chat.
- Configuracoes: API keys por provedor, registry editavel de modelos e secao "Modelagem 3D" (Blender path, Fusion MCP URL, transport, timeouts, status de adapters).
- Arquivos: biblioteca bruta de arquivos enviados, recebidos, gerados ou importados, com paginacao, filtros, preview/download e status de indexacao.
- Bases: colecoes curadas de documentos indexados para RAG.
- Projetos: organizacao de chats e pastas, com bases atreladas quando fizer sentido.

## Documentacao

`apps/docs` roda Docusaurus em `http://127.0.0.1:3000`.

Ele nao duplica a documentacao: le diretamente os arquivos Markdown da pasta `docs/` do monorepo (`path: "../../docs"` no Docusaurus).

## SDD

O SDD vive em `specs/` e organiza intenção, plano, tasks e handoff sem substituir `docs/`.

- `AGENTS.md`: contrato comum de arquitetura, prioridade de contexto e qualidade.
- `CLAUDE.md`: adaptador mínimo para Claude Code carregar `AGENTS.md`.
- `specs/repo-foundation/spec.md`: baseline do MVP local-first.
- `specs/repo-foundation/plan.md`: plano técnico e sequência de workstreams.
- `specs/repo-foundation/tasks.md`: backlog rastreável por prioridade e executor sugerido.
- `specs/repo-foundation/handoff.md`: continuidade quando humanos, Codex, Claude Code ou Devin alternarem a execução.
- `specs/<slug-do-dominio>/`: specs por domínio para agentes/tools, RAG, mobile, artifacts/export, 3D/Fusion e observabilidade.
- `docs/delivery-checklist.md`: checklist obrigatório de entrega para PRs e handoffs.
- `.agents/skills/`: skills instruction-first para mapear repo, validar qualidade e trabalhar nos principais bounded contexts.

## Dados

- Postgres guarda estado transacional em tabelas JSONB: chats, mensagens, modelos, agentes, prompts, projetos, pastas, documentos, arquivos, bases, importacoes, auditoria, politica de custo e modelagem 3D.
- Qdrant guarda vetores dos documentos indexados.
- Valkey/Redis esta preparado para cache/fila, mas os workers atuais de importacao/indexacao rodam em memoria no processo do backend.
- `.local/files` guarda documentos locais.
- `.local/state` guarda segredos cifrados, estado local auxiliar e o discovery default do bridge Fusion quando o backend usa `settings.state_dir`.
- `.local/imports` guarda uploads de exportacao do ChatGPT.
- `.local/modeling` guarda workspaces, snapshots e artefatos 3D gerados.

## Fluxo de chat

1. Usuario cria chat (com titulo obrigatorio nao vazio — ADR-014) e opcionalmente marca como 3D.
2. Usuario envia mensagem no React.
3. Frontend chama `POST /api/chat/stream`. Backend rejeita com 422 se `chat.title` ausente.
4. Backend resolve agente principal, agente solicitado, agentes de apoio e bases atreladas.
5. Se `chat.is_modeling_3d=true`, o agente segue a state machine `discovery → planning → approved → executing → editing` (ADR-013). Tools dedicadas (`3d.ask_clarification`, `3d.propose_plan`, `3d.propose_edit_plan`, `3d.request_high_risk_approval`, `3d.analyze_attachment`) controlam transicoes.
6. Caso contrário, backend escolhe o modelo pelo Model Registry.
7. Cost Governor estima custo antes da chamada.
8. LLM Gateway chama o provedor real ou fallback dev. Modos especiais (Deep Research, imagem, resumo oficial) seguem mutuamente exclusivos com chat 3D.
9. Imagens geradas, anexos e exports 3D viram `PlatformFile` em `Arquivos` e podem ser indexados.
10. Backend envia tokens via SSE; eventos `modeling_plan`, `modeling_edit` e `modeling_execution` levam estado 3D para a UI.
11. Mensagens, metadados e auditoria sao salvos no store.

## Fluxo de RAG

1. Arquivos entram pela biblioteca `Arquivos`, por upload, importacao ou geracao.
2. O backend extrai texto/metadados e indexa chunks no Qdrant.
3. O usuario organiza documentos em `Bases de conhecimento`.
4. Projetos e agentes podem referenciar bases.
5. No chat, o backend busca apenas nas bases ativas para aquele agente/projeto.
6. O Qdrant ranqueia semanticamente os chunks e o backend aplica regras de escopo, prioridade e limite antes de montar o prompt.
