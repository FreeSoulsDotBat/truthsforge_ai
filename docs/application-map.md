# Mapa da aplicacao

## Monorepo

O projeto e um monorepo: backend, frontends, documentacao, pacotes compartilhados e infra vivem no mesmo repositorio.

- `backend`: API, regras de negocio, providers LLM, storage, RAG e agentes.
- `apps/web`: interface principal em React.
- `apps/docs`: documentacao Docusaurus que le a pasta `docs`.
- `apps/desktop`: wrapper Tauri para desktop.
- `apps/mobile`: wrapper Capacitor para Android.
- `packages/types`: espaco para tipos compartilhados.
- `packages/ui`: espaco para componentes compartilhados.
- `infra`: Docker Compose e configuracao dos servicos locais.
- `docs`: documentacao do produto, arquitetura e operacao.
- `.local`: dados locais ignorados pelo Git.

## Backend

O backend e uma aplicacao FastAPI. Ele expoe rotas REST e streaming SSE para o chat.

- `api`: roteadores HTTP.
- `core`: configuracoes e contratos centrais.
- `llm_gateway`: camada que conversa com OpenAI, Anthropic e Google.
- `judite`: persona/orquestracao inicial da JUDITE.
- `agents`: preparacao para LangGraph/LangChain.
- `rag`: embeddings, VectorStore e Qdrant.
- `files`: deteccao, chunking e storage de documentos.
- `prompts`: biblioteca e renderizacao de prompts.
- `tools`: catalogo de ferramentas internas.
- `security`: segredos e permissoes.
- `audit`: eventos de auditoria.
- `cost_governor`: orcamento, estimativa de custo e uso mensal.
- `storage`: persistencia em Postgres com fallback JSON.
- `workers`: base para jobs longos.
- `modeling`: bounded context de modelagem 3D via MCP local, com planner, politica, adapters e execução segura do Blender quando disponível.

## Frontend web

O frontend React e a primeira experiencia do usuario.

- Sidebar esquerda: sessoes, historico e novo chat.
- Centro: chat com streaming.
- Painel direito: contexto, custos, RAG, auditoria, prompts e configuracao.
- Configuracoes: API keys por provedor e registry editavel de modelos.
- Arquivos: biblioteca bruta de arquivos enviados, recebidos, gerados ou importados.
- Bases: colecoes curadas de documentos indexados para RAG.
- Projetos: organizacao de chats e pastas, com bases atreladas quando fizer sentido.

## Documentacao

`apps/docs` roda Docusaurus em `http://127.0.0.1:3000`.

Ele nao duplica a documentacao: le diretamente os arquivos Markdown em `D:\projects\truths_forge_ai\docs`.

## Dados

- Postgres guarda estado transacional: chats, mensagens, modelos, agentes, prompts, documentos, auditoria e politica de custo.
- Qdrant guarda vetores dos documentos indexados.
- Valkey/Redis esta reservado para cache/fila.
- `.local/files` guarda documentos locais.
- `.local/state` guarda segredos cifrados e estado local auxiliar.
- `.local/modeling` guarda workspaces, snapshots e artefatos 3D gerados.

## Fluxo de chat

1. Usuario envia mensagem no React.
2. Frontend chama `POST /api/chat/stream`.
3. Backend escolhe o modelo pelo Model Registry.
4. Cost Governor estima custo antes da chamada.
5. LLM Gateway chama o provedor real ou fallback dev.
6. Backend envia tokens via SSE.
7. Mensagens e auditoria sao salvas no Postgres.

## Fluxo de RAG

1. Arquivos entram pela biblioteca `Arquivos`, por upload, importacao ou geracao.
2. O backend extrai texto/metadados e indexa chunks no Qdrant.
3. O usuario organiza documentos em `Bases de conhecimento`.
4. Projetos e agentes podem referenciar bases.
5. No chat, o backend busca apenas nas bases ativas para aquele agente/projeto.
6. O Qdrant ranqueia semanticamente os chunks e o backend aplica regras de escopo, prioridade e limite antes de montar o prompt.
