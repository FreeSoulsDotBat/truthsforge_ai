# Decisoes

## ADR-001 - Monorepo

Usar um unico repositorio com frontend compartilhado, wrappers desktop/mobile, backend e infra. Isso reduz atrito para uma aplicacao pessoal e facilita evoluir contratos entre UI e API.

## ADR-002 - FastAPI e Python

Backend em Python 3.11 com FastAPI para favorecer processamento de arquivos, RAG, engenharia de prompts, agentes e ciencia de dados.

## ADR-003 - React/Vite + Tauri + Capacitor

Uma base React responsiva gera web, desktop e mobile. Tauri fica como wrapper Windows e Capacitor como wrapper Android. Instaladores completos ficam depois do dev loop estar estavel.

## ADR-004 - Postgres + Qdrant

Postgres e a fonte transacional de producao local. Qdrant e o indice vetorial principal por performance, filtros e tuning dedicado. O backend usa a interface `VectorStore` para permitir troca futura para pgvector/LanceDB.

O store JSON permanece apenas como fallback de desenvolvimento/testes quando Postgres nao esta disponivel. Ele nao deve ser tratado como formato de producao, nem como caminho de sincronizacao entre dispositivos. Para rodar o produto completo, use Postgres + Qdrant + Valkey pelo Docker Compose.

O modulo 3D pode guardar arquivos pesados no filesystem local e metadados no store principal. Apesar da proposta inicial de SQLite para um servico 3D isolado, a aplicacao consolidada mantem Postgres como fonte transacional unica para reduzir divergencia entre chat, agentes, RAG, auditoria, custos e modelagem.

Payloads `JSONB` sao aceitos no MVP para acelerar iteracao. Quando houver volume real, as rotas mais quentes devem ser normalizadas primeiro: mensagens, chunks/documentos, auditoria, permissoes, tool calls e politicas de retencao.

## ADR-005 - LangGraph/LangChain para agentes

LangGraph/LangChain entram para fluxos agentic com estado, checkpoint humano e multiplos passos. A aplicacao ainda mantem politicas, permissoes e auditoria em codigo proprio.

## ADR-006 - Seguranca mobile

O acesso remoto padrao sera por Tailscale/WireGuard. Portas HTTPS publicas ficam fora do MVP inicial para reduzir risco.

## ADR-007 - Modelos locais

Chat fica restrito a OpenAI, Anthropic e Google. Modelos locais podem ser usados para embeddings, reranking, OCR auxiliar e outras tarefas de infraestrutura que reduzam custo.

## ADR-008 - Governança SDD por domínio

Mudanças relevantes devem referenciar uma spec/task. Quando a frente exceder ajuste pontual, a spec deve viver em `specs/<slug-do-dominio>/`, separada do baseline `repo-foundation`.

Toda entrega relevante deve incluir o checklist obrigatório de `docs/delivery-checklist.md`. Antes de alterar a plataforma, o executor deve confirmar com o dono do produto o nome da branch e a mensagem de commit em formato semântico.

## ADR-009 - Autonomia de agentes e tools

JUDITE deve evoluir como orquestradora que delega contexto e coordena workflows multi-etapa com checkpoints humanos. Agentes e tools podem executar adições sem aprovação quando a policy permitir. Alterações e deleções exigem aprovação humana.

Tools de escrita ou execução devem operar em diretório isolado por projeto, com rede permitida no MVP, timeout e limites de tamanho definidos pela implementação, auditoria e rollback obrigatório.

## ADR-010 - RAG, dados sensíveis e provedores externos

Documentos indexados podem compor prompts enviados a OpenAI, Anthropic ou Google quando esses provedores estiverem configurados. Conteúdo sensível deve ser classificado por controle manual e heurística automática, com rastreabilidade na auditoria.

O fluxo automático assistido de importação ChatGPT para bases revisadas não faz parte do MVP imediato.

## ADR-011 - Mobile MVP sem autenticação de usuário

O pareamento mobile inicial deve usar QR code local. Para o MVP, não haverá autenticação de usuário no mobile; o cliente pareado pode manter cache offline completo.

## ADR-012 - 3D/Fusion obrigatório no MVP

Blender real e Fusion bridge são obrigatórios para a trilha atual de modelagem 3D. Fusion deve ser tratado como spec própria do bounded context 3D, com planner, policy, snapshots, rollback, printability, exports e artifacts rastreáveis.
