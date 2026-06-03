# Micro-plano — Fase 2: Núcleo agêntico

**Fase**: 2 | **Spec**: [`../spec.md`](../spec.md) (RF-005/006/007, RF-008/009/010/011, RF-012/013, RF-019, RF-024/025) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de**: Fase 1 (servidor MCP standalone + gate). Insumos: `chat-flow-redesign.md` (fluxo) e `observability-plan.md` (observabilidade).

## Objetivo

Construir o cérebro do produto: após o usuário aprovar o plano, o motor **executa do início ao fim, sem parar**, com um **loop interno de auto-correção** (`executa → inspeciona → corrige`, teto 5) e **verificação geométrica por read-back** (esperado × medido). Persistir chat + histórico de modelagem de forma reconstituível e tornar a observabilidade legível para o dono.

## Estado atual (ponto de partida)

- `chat_orchestrator.py` + `chat_state.py` — state machine descoberta → planejamento → execução → edição.
- `discovery.py` — clarificação; `planner.py`/`planner_service.py` — geração de plano; `policy.py` — risco/aprovação.
- `executor.py` — executa passos (base do loop).
- `observability.py` — traces; `snapshot_service.py` — snapshots/rollback.
- **Integrado nesta branch** (commit `06b2d2e`): `agent_loop.py` (`ModelingAgentLoop`, teto duro 5), `tool_schemas.py` (a LLM vê args/unidades/exemplos) e `planner.build_correction_context` (edit-context + falhas). O loop está **ligado ao stream** após a aprovação (flag `modeling_agentic_loop_enabled`), dispara correção em `status=failed` **e** em divergência geométrica (verifier injetável), e **não pausa** para corretivo high-risk (decisão do dono — DT-010). **Validado end-to-end no Fusion real** (Gate 4, commit `9b4fd4b`, 2026-05-29: cubo+fillet 16mm impossível → corretor LLM reduziu → completed). _Resíduo aberto:_ snapshot nativo do Fusion (DT-005, hoje `rollback_skipped`) e read-back geométrico fiado no loop em peça real.

## Recorte do trabalho (decidido com o dono, 2026-05-24)

A Fase 2 mistura partes que **não dependem do Fusion real** (estruturais, validáveis em CI) com partes que **dependem** (loop real, verificação geométrica) — estas esperam a **convergência de branches** (assets do fidelity) **e** o gate da Fase 1. Sequência aprovada: começar pelo estrutural já.

**Estrutural — agora (sem Fusion):**
- **DT-007** (T2.11) — fallback JSON explícito (logar degradação `auto`→JSON). ✅ **feito** (`storage/store.py` + `test_store_fallback.py`).
- **DT-008** (T2.12) — estado de falha/correção distinto em `chat_state`/`ChatModelingStage` (hoje `EXECUTION_FAILED→editing`, indistinguível de sucesso). _Mudança de contrato_ — ver design abaixo.
- **DT-006** (T2.9) — promover o `ModelingChatOrchestrator` ao caminho vivo; enxugar `api/routes/chat_modeling.py`. _Refactor do caminho vivo_ — ver reconciliações abaixo.
- **Executor (prep do loop)** — fatiar `execute_plan` e abrir um **ponto de extensão** para a correção, sem mudar comportamento (T2.3 vira plugável).

**Depende de Fusion/convergência — adiado:** T2.2 (read-back), T2.3 (ligar `ModelingAgentLoop` ao stream), T2.3b (correção por divergência geométrica), T2.10 (snapshot nativo — DT-005), e o gate Nível 1.

### DT-006 — reconciliações descobertas na leitura (rota × orchestrator)

A promoção **não é troca mecânica**; há 2 divergências de comportamento a reconciliar para não regredir o chat:

1. **Modo fluido (opt-in).** `orchestrator.propose_edit_plan` auto-executa **todo** edit não-high-risk; a rota só auto-executa quando `session.modeling_fluid_mode` está ligado (chat-flow-redesign: fluido é opt-in). → **Plano**: parametrizar a decisão de auto-exec por `fluid_mode` (passar flag ao orchestrator), preservando o gate de card quando fluido OFF.
2. **Gate P1 de `waiting_approval`.** A rota força `plan.status = waiting_approval` para o card mostrar Aprovar/Rejeitar mesmo quando o planner marcou `approved`; `propose_plan` move só o **estágio do chat** (`planning`). → **Plano**: manter o gate de status do plano na borda (rota/serviço), usando o orchestrator para a transição de **estágio** (state machine única).

Concerns de borda preservados na rota (SSE/mensagens/título/trace): a rota continua dona do streaming; o orchestrator passa a ser dono das **transições de estágio** (via `chat_state`) e dos eventos `modeling.chat.*`. `propose_plan`/`propose_edit_plan` são síncronos → chamar com `asyncio.to_thread` (como já se faz com `execute_plan`). Estratégia de teste: **paridade de comportamento** (discovery/clarificação, intent ambíguo, fluido ON/OFF, gate P1, título, erro) antes e depois.

### DT-008 — design do estado de falha (proposto)

Adicionar `ChatModelingStage.failed` (e evento `EXECUTION_FAILED` passando a apontar para `failed` em vez de `editing`). De `failed`: `→ editing` (usuário corrige/continua), `→ discovery` (recomeça) e `→ executing` (retry). **Atenção**: muda o teste `test_execution_failed_still_lands_in_editing` (comportamento hoje intencional) e pode afetar a UI que lê `modeling_stage`. Confirmar antes de codar.

## Decisões-chave

1. **Oráculo de verificação**: cada `ModelingStep` carrega valores dimensionais **esperados**; após executar, o motor lê a geometria (bbox, volume, contagens, dimensões) via tool de read-back e compara. Divergência alimenta a correção (RF-012/013).
2. **Loop**: teto **5 iterações** por ponto de falha; término **sempre explícito** (sucesso ou falha reportada); ao esgotar, **rollback** ao último snapshot seguro (RF-010/011).
3. **Execução atômica**: sem pausa nem validação passo-a-passo após a aprovação; aprovação única cobre high-risk (RF-008/009).
4. **Persistência (P5)**: chat + plano + passos executados + verificações + traces em Postgres (fallback JSON dev) — reconstituível (RF-019).
5. **Observabilidade**: trace por passo + logs legíveis pelo dono na UI; **doc de scripts de terminal de debug** (RF-024/025).

## Tarefas atômicas

- **T2.1** — Estender o contrato de `ModelingStep`/plano com **geometria esperada** por passo (dimensões/contagens/bbox quando aplicável).
- **T2.2** — Implementar tool de **read-back geométrico** (query de bbox/volume/contagens/dimensões) exposta pelo servidor MCP. _(dependente do adapter; validada no gate)_
- **T2.3** ✅ (núcleo) — `agent_loop.py` (`ModelingAgentLoop`) **implementado do zero** (os assets do fidelity não existiam — ver convergência): teto 5, término explícito, rollback ao esgotar (RF-011), plugando na costura `_execute_single_step`; corretor/verifier/rollback **injetáveis**. Testado com mock (sucesso, corrige-e-passa, esgota+rollback, divergência). **Pendente**: ligar ao stream (flag `modeling_agentic_loop_enabled` + orchestrator) e o **corretor LLM** (qualidade só no gate do Fusion).
- **T2.3b** ✅ (estrutura) — `_needs_correction` dispara em `status=failed` **e** em divergência via `verifier` injetável (read-back esperado × medido). O read-back real depende do Fusion (gate).
- **T2.3c** ✅ — `tool_schemas.py` criado (args/unidades mm/exemplos canônicos por tool + render). **Pendente**: injetar no prompt do planner (`_build_messages`).
- **T2.3d** ✅ — `planner.build_correction_context` implementado (erro + args + verificação → contexto de correção da LLM).
- **T2.4** — Garantir **execução fim-a-fim sem pausa** após aprovação; aprovação única cobrindo high-risk, **inclusive deltas corretivos** (ajustar `agent_loop` para não bloquear corretivo high-risk — DT-010, decisão do dono).
- **T2.5** — **Persistência** do histórico de modelagem (esquema Postgres + fallback JSON; impacto em `postgres`/`json`/`auto` explicitado).
- **T2.6** — **Observabilidade**: trace por passo + relatório de verificação na UI; superfície de logs legível ao dono.
- **T2.7** — Escrever a **doc de scripts de debug** (terminal) por classe de erro (em `docs/` ou `observability-plan.md`).
- **T2.8** — Testes: loop (sucesso, correção, esgotamento+rollback), verificação (conforme/divergente), persistência, fluxo fim-a-fim com adapter mock.

### Correções estruturais achadas na varredura

- **T2.9 (DT-006, clean architecture)** — Consolidar o fluxo na `ModelingChatOrchestrator`; remover regra de negócio e a state machine duplicada de `api/routes/chat_modeling.py` (rota fica fina). Execução passa a ocorrer pelo chat (não por `card.approve`+`card.execute`).
- **T2.10 (DT-005)** — Redesenhar snapshot/rollback para capturar **estado nativo do Fusion** (timeline/B-Rep), não cópia de filesystem — pré-condição do rollback de RF-011.
- **T2.11 (DT-007)** ✅ — Persistência **explícita**: falha do Postgres no modo `auto` não cai em JSON silenciosamente (loga a degradação); modo `postgres` re-levanta. Feito em `storage/store.py` + `test_store_fallback.py`.
- **T2.12 (DT-008)** — Adicionar transição de **falha/rollback** distinta em `chat_state` (não tratar `EXECUTION_FAILED` igual a sucesso).

## Contratos / invariantes

- Nenhuma pausa para o usuário entre aprovação e término (RF-008).
- Teto de 5 iterações respeitado; falha terminal nunca deixa modelo inconsistente silencioso (RF-011).
- Snapshot/rollback/auditoria obrigatórios; allowlist de fonte única (P8/RF-022/023).

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest`.
- Web: `format:check`, `lint`, `test:unit`, `typecheck`, `build` (UI de diagnóstico/verificação).
- **Gate do dono (Fusion real)**: modelar **uma peça Nível 1** (suporte paramétrico com furos e fillets) por chat, do pedido ao resultado, sem intervenção manual; revisar trace por passo + relatório esperado × medido.

## Riscos

- **Read-back limitado pelo adapter** → oráculo fraco. Mitigação: validar a tool de read-back no Fusion real cedo; degradar para verificação parcial declarada.
- **Loop custoso/instável** → custo e tempo. Mitigação: teto 5 + métricas de iteração + término explícito.
- **Esquema de persistência** mexe em storage → P5. Mitigação: explicitar `postgres`/`json`/`auto`; migração isolada.

## Definição de pronto (Fase 2)

- [x] Loop agêntico com teto 5, término explícito e rollback (`agent_loop.py`, validado Gate 4 — 2026-05-29).
- [x] Verificação geométrica esperado × medido por passo (verifier injetável + `_needs_correction` dispara em divergência).
- [x] Execução fim-a-fim sem pausa; aprovação única cobre high-risk (loop não pausa em corretivo high-risk — DT-010).
- [x] Persistência de chat + histórico de modelagem (Postgres/JSON; exercitada no end-to-end).
- [x] Observabilidade legível + doc de scripts de debug (`docs/3d-modeling-debug.md`).
- [~] Rota fina + fluxo consolidado no orchestrator (DT-006 ✅); **snapshot nativo do Fusion (DT-005) ainda aberto** (hoje `rollback_skipped`); persistência explícita (DT-007 ✅); estado de falha no `chat_state` (DT-008 ✅ — `ChatModelingStage.failed`).
- [x] Testes verdes; **gate do dono (Nível 1 / Gate 4) aprovado** end-to-end no Fusion real (2026-05-29). _Pendente:_ read-back geométrico fiado no loop em peça real + snapshot nativo (DT-005).
