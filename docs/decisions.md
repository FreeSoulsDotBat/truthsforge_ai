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

Blender real e Fusion conectado são obrigatórios para a trilha atual de modelagem 3D. Fusion deve ser tratado como spec própria do bounded context 3D, com planner, policy, snapshots, rollback, printability, exports e artifacts rastreáveis. O caminho preferido é o Fusion MCP Server local do próprio aplicativo (`/mcp` na porta exibida pelo Fusion, padrão `27182`); o bridge loopback legado permanece apenas como fallback compatível.

## ADR-013 - 3D chat-first integral; remoção do painel; aprovação inline

A experiência de modelagem 3D passa a ser **integralmente conduzida pelo chat**. O painel 3D do dashboard é removido. Configuração de adapters (Blender path, Fusion MCP URL, transports) migra para Configurações gerais. Diagnóstico operacional (capabilities, sessões, snapshots, tool calls, model versions, printability reports) vira modal read-only acessível pelo cabeçalho do chat 3D.

Cada chat marcado como 3D segue uma **state machine única**:

```
created (title obrigatório) → discovery → planning → approved → executing → editing ↺
                                              ↑                                ↓
                                              └────── (rejeição) ──────────────┘
```

A flag `is_modeling_3d` é por chat, persistida e imutável após criação. Ativar 3D em um chat com histórico não-vazio abre modal que oferece criar um novo chat 3D vazio; não há cópia de mensagens entre chats.

Os modos legados `plan_only`, `approval_required` e `safe_auto` são **removidos** e o backend deixa de aceitá-los. Sempre que o agente julgar que tem contexto suficiente, ele chama a tool `3d.propose_plan` e o backend transiciona o chat para `planning`. O plano aparece no chat como `ModelingPlanCard` com prosa, etapas, badges de risco, banner de aviso para etapas high-risk e dois botões: "Aprovar" e "Rejeitar" (com campo opcional de motivo). Texto livre **não** aciona execução.

A aprovação global do plano cobre todas as etapas, incluindo high-risk (`apply_boolean`, `repair_non_manifold`, `restore_snapshot`, `run_script`). Não há mais aprovação step-a-step após o plano primário aprovado. Edições posteriores (estado `editing`) geram mini-planos auto-aprovados quando só contêm tools allowlistadas não-high_risk; ao tocar em high-risk, o card volta a pedir aprovação inline. Snapshots manuais, rollback explícito, allowlist e auditoria permanecem como guardrails obrigatórios.

A descoberta de contexto aceita anexos com análise profunda: imagens via vision do gateway LLM e arquivos 3D (`STL`/`OBJ`/`STEP`/`3MF`/`BLEND`) via Blender headless extraindo bounding box, contagens, volume, simetria, features e sugestões iniciais.

A allowlist de tools deixa de viver em três arquivos espalhados (`planner.py`, `policy.py`, adapters) e passa a derivar de uma única fonte (`backend/app/modeling/tool_registry.py`) para eliminar divergência silenciosa.

A trajetória de implementação está descrita em `specs/005-modeling-3d-fusion/plan.md` (6 ondas: docs/ADRs → backend foundations → backend chat orchestration → frontend feature module → frontend cards/aprovação → título obrigatório → QA/handoff).

## ADR-014 - Título de chat obrigatório; remoção da auto-titulação OpenAI

Todo chat (3D ou não) passa a exigir título não vazio antes da primeira mensagem. O frontend bloqueia o input de envio e exige nomeação imediata; o backend rejeita `POST /api/chat/stream` com `HTTP 422` quando `chat.title` estiver ausente ou vazio.

O serviço/endpoint atual que chama a OpenAI para gerar título automático é **removido**, eliminando consumo de tokens dessa chamada. A migração que torna `chats.title NOT NULL` aplica backfill `"Sem título - YYYY-MM-DD"` (derivado de `created_at`) aos chats existentes para preservar dados sem quebrar a constraint.

A motivação combina três pontos: (1) economia de tokens em uma chamada que não agrega valor consistente, (2) clareza explícita de propósito do chat desde o início, (3) suporte ao novo fluxo 3D, onde o título distingue rapidamente sessões de modelagem na sidebar (junto com o `ChatModeling3DBadge`).

Renomeação posterior do chat continua permitida via UI. A obrigatoriedade vale apenas para a transição "chat criado → primeira mensagem enviada".

## ADR-015 - Abstração de storage (interface Store)

A camada de storage passa a ter uma **interface única** descrita por um `typing.Protocol` `Store` em `backend/app/storage/`, derivada da superfície atual já compartilhada por `PostgresStore` (`postgres_store.py`) e pelo dev-store JSON (`dev_store.py`). `get_store()` (`storage/store.py`) passa a ser tipado como `Store`.

Motivação: hoje os dois stores duplicam ~46 métodos sem contrato comum (~3390 linhas), o que gera risco de divergência silenciosa quando uma assinatura muda em apenas um deles.

A decisão **não troca a stack** (P5/ADR-004 permanecem: Postgres é produção; JSON é apenas dev/test). A implementação é **faseada e de baixo risco**: (1) teste de paridade que garante superfície idêntica entre os dois stores; (2) `Protocol Store` extraído da superfície atual, sem alterar implementações; (3) opcionalmente, fatiamento futuro em repositórios por domínio, um por vez, com testes. Cada fase roda os gates de `scripts/quality.ps1` antes de concluir.

Spec e plano: `specs/070-storage-persistence/` (ver `research.md`).

## ADR-016 - Geração de tipos do contrato a partir do OpenAPI

Os tipos do contrato consumidos pelo frontend deixam de ser mantidos à mão em `apps/web/src/types/api.ts` (740 linhas) e passam a ser **gerados a partir do OpenAPI do backend** (`apps/web/src/types/openapi.json`, hoje já exportado mas não usado), via `openapi-typescript` (ou equivalente leve).

Motivação: eliminar o drift silencioso entre backend e frontend, no qual uma mudança de contrato no FastAPI não se reflete nos tipos manuais.

Por ser **mudança de toolchain de build** (nova dependência de dev + passo de geração), a adoção entra em um PR controlado próprio, com `typecheck`/`build` verdes e os tipos gerados versionados ou gerados no build. Sem dependências pesadas em runtime (P-Frontend de `AGENTS.md`).

Spec e plano: `specs/090-frontend-web-shell/` (dívida DT-003).
