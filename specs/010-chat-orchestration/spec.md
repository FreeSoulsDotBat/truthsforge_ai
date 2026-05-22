# Especificação: Orquestração de Chat (núcleo)

**Pasta da spec**: `specs/010-chat-orchestration/` | **Criada em**: 2026-05-22 | **Status**: Rascunho

**Entrada**: Cobrir com spec o bounded context central de chat, hoje sem spec dedicada (existia só como baseline em `repo-foundation`).

> Onda 1 do refactor SDD. Documenta o **comportamento atual** do chat e a **dívida de código** do monólito `chat.py`. O 3D tem spec própria (`modeling-3d-fusion`); aqui cobrimos apenas o ponto de integração.

## Cenários de usuário e testes

### História 1 — Conversar com streaming (Prioridade: P1) 🎯 MVP

O operador envia uma mensagem num chat e recebe a resposta em streaming, com a interação persistida.

**Por que esta prioridade**: é a função central do produto.

**Teste independente**: enviar mensagem em `POST /api/chat/stream` e observar eventos SSE incrementais + mensagem persistida.

**Cenários de aceitação**:

1. **Dado** um chat com título válido, **Quando** o operador envia uma mensagem, **Então** o sistema responde com tokens em streaming e persiste a mensagem do usuário e do assistente.
2. **Dado** provider/modelo não configurado, **Quando** há mensagem, **Então** o sistema falha de forma explícita ou usa o fallback dev quando `allow_dev_llm` permitir.

### História 2 — Orquestração de agentes e contexto (Prioridade: P1)

O sistema resolve agente principal (JUDITE/orquestrador), agente alvo e agentes de apoio, e injeta contexto (projeto, bases ativas, menções `@folder`, RAG).

**Cenários de aceitação**:

1. **Dado** múltiplos agentes ativos, **Quando** há mensagem, **Então** o sistema seleciona orquestração via `select_orchestration_agents` e monta o histórico com o contexto permitido pelo escopo.

### História 3 — Governança de custo no envio (Prioridade: P1)

Antes de chamar a LLM, o sistema estima custo (preflight) e bloqueia quando a política exige.

**Cenários de aceitação**:

1. **Dado** orçamento mensal estourado ou pricing ausente para um modo que exige (Deep Research, imagem, reasoning summary), **Quando** há envio, **Então** o sistema bloqueia (HTTP 402) e registra auditoria `chat.blocked`.

### História 4 — Modos especiais mutuamente exclusivos (Prioridade: P2)

Deep Research, geração de imagem, reasoning summary (só OpenAI) e modelagem 3D são caminhos mutuamente exclusivos.

### Casos de borda

- Título ausente/vazio na primeira mensagem → bloqueio (ADR-014).
- Anexos fora do escopo do projeto → erro de escopo.
- Provider configurado mas sem pricing para o modo escolhido → bloqueio explícito.

## Requisitos

### Requisitos funcionais

- **RF-001**: QUANDO o operador envia uma mensagem em um chat, O SISTEMA DEVE responder via SSE e persistir a interação (`store.add_message`).
- **RF-002**: QUANDO há múltiplos agentes, O SISTEMA DEVE resolver principal/alvo/apoio via `select_orchestration_agents` (`backend/app/api/routes/chat.py:647`).
- **RF-003**: QUANDO uma base de conhecimento estiver ativa no escopo, O SISTEMA DEVE buscar apenas no escopo permitido antes de montar o contexto (`_knowledge_base_ids_for_runtime`, `_search_knowledge_base_context`).
- **RF-004**: QUANDO o envio exceder a política de custo ou faltar pricing para um modo que exige, O SISTEMA DEVE bloquear com HTTP 402 e registrar `chat.blocked` (`record_audit_event`).
- **RF-005**: QUANDO o chat não tiver título válido na primeira mensagem, O SISTEMA DEVE rejeitar com erro `chat_title_required` (`_enforce_required_chat_title`, `chat.py:623`) — ADR-014.
- **RF-006**: QUANDO `modeling_3d.enabled` for verdadeiro, O SISTEMA DEVE bifurcar para o fluxo 3D (bounded context separado) sem executar inline — ADR-013.
- **RF-007**: O SISTEMA DEVE emitir os eventos SSE via `_sse()` (`chat.py:1153`): `status`, `meta`, `token`, `reasoning_summary`, `session_title`, `modeling_plan`, `error`, `done`.
- **RF-008**: QUANDO a resposta concluir, O SISTEMA DEVE registrar auditoria `chat.stream` com agentes, modo, tokens e custo final estimado.

### Requisitos não funcionais

- **RNF-001**: O fluxo DEVE preservar os prefixos de rota existentes (`/api/chat`) e o contrato SSE atual (P3 preservar arquitetura).
- **RNF-002**: Chamadas LLM e custo DEVEM ser auditáveis (P9; `docs/infra-observability.md`).

## Critérios de sucesso

- **CS-001**: 100% dos envios concluídos geram um evento de auditoria (`chat.stream` ou `chat.blocked`).
- **CS-002**: Nenhum modo especial (Deep Research/imagem/reasoning/3D) executa combinado com outro.

## Premissas

- O fallback dev (`judite/orchestrator.py`) só responde quando `allow_dev_llm` está habilitado.
- A spec descreve o comportamento atual; mudanças de contrato exigem atualizar esta spec e `docs/`.

## Fontes

- Constituição: `.specify/memory/constitution.md`
- Código: `backend/app/api/routes/chat.py` (rota e orquestração), `backend/app/api/router.py` (prefixo `/api/chat`), `backend/app/chat/session_cleanup.py`, `backend/app/judite/orchestrator.py`, `backend/app/agents/graph.py`, `backend/app/cost_governor/service.py`, `backend/app/llm_gateway/gateway.py`, `backend/app/llm_gateway/model_registry.py`, `backend/app/audit/service.py`
- Docs: `docs/application-map.md`, `docs/deep-research.md`, `docs/image-generation.md`, `docs/reasoning-summary.md`, `docs/decisions.md` (ADR-013, ADR-014)
- Testes: `backend/tests/test_chat_orchestrator.py`, `test_chat_title_required.py`, `test_chat_modeling_state_machine.py`, `test_chat_attachment_analyze_endpoint.py`, `test_agent_orchestration.py`, `test_runtime_routes.py`
- Specs relacionadas: `specs/005-modeling-3d-fusion/` (3D), `specs/050-agents-tools-runtime/` (agentes/tools), `specs/060-cost-audit-governance/` (custo/auditoria), `specs/030-files-rag-pipeline/` (RAG)

## Dívida de código documentada *(não executar nesta frente)*

- **DT-001**: `backend/app/api/routes/chat.py` é um **monólito de 2433 linhas** que mistura, no route layer, orquestração de fluxo, helpers de imagem, escopo de projeto, RAG, glue de 3D e auditoria. O split "monólitos de borda" (`chat_context/chat_images/chat_modeling/chat_scope/chat_sse`) **não existe** no código. Direção: extrair um `chat/` service layer (orquestração, contexto/RAG, SSE, modos especiais) e deixar a rota fina. Esforço: L. ADR necessário? Recomendado (padrão service layer — ver `070-storage-persistence`/futuro ADR de camadas).
- **DT-002**: `stream_chat` acessa `get_store()` direto (`chat.py:1404`), sem injeção de dependência — dificulta teste isolado. Direção: `Depends()` + service. Esforço: M.
- **DT-003**: glue de 3D inline em `chat.py` (`_modeling_*`, `_promote_modeling_session`) acopla o núcleo ao bounded context 3D. Direção: mover para a fronteira do contexto 3D. Esforço: M.

## Verificação de qualidade da spec

- [x] Sem detalhe de implementação nos requisitos além do necessário para rastreabilidade
- [x] Requisitos testáveis (EARS) com Fontes válidas
- [x] Critérios de sucesso mensuráveis
- [x] Constituição referenciada em Fontes
- [x] Dívida documentada (não executada)
