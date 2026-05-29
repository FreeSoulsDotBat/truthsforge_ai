# Micro-plano — Frente F2: Planejamento agêntico/hierárquico

**Frente**: F2 | **Spec**: [`../spec.md`](../spec.md) | **Macro**: [`../plan.md`](../plan.md) › Frentes de capacidade | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de F1** (estado rico). Realiza P2 (planejamento minucioso + estado compartilhado entre etapas). Replan 2026-05-29.

## Objetivo

Trocar o planejamento **one-shot e flat** (`planner.create_llm_plan` gera a lista inteira de uma vez) por um loop **decompor → executar → observar → replanejar**: o LLM decompõe o pedido em sub-objetivos verificáveis e planeja cada bloco fino **observando o `ModelState` real** (F1) deixado pelo bloco anterior. É o que viabiliza peças mecânicas onde um passo depende da medida real do anterior (ex.: furo da fêmea com o diâmetro real do pino macho).

## Estado atual (gargalo)

- `planner.create_llm_plan` (~402): um disparo, lista linear, sem sub-objetivos nem replanejamento.
- `agent_loop.ModelingAgentLoop` (~106) + `run_plan_with_optional_loop` (:372): já faz executa→inspeciona→corrige por **step** (teto 5). É correção de step, não replanejamento de plano.

## Decisões-chave

- **D4** — F2 é evolução do `ModelingChatOrchestrator` (`_run_execution_hierarchical`), atrás de NOVA flag `modeling_hierarchical_planning_enabled` (default OFF), convivendo com o fluxo atual. **Reusa o `ModelingAgentLoop`** por baixo (correção de step de graça). (Rejeitado serviço dedicado — duplica fiação + briga com DT-006.)
- **D5** — schemas isolados: `DECOMPOSITION_SCHEMA` (sub-objetivos + critério de aceitação) novo; reuso de `EXECUTION_PLAN_SCHEMA` por bloco. (Rejeitado schema recursivo único.)
- **Lazy planning** — o planejamento dos steps finos de cada bloco acontece **na execução** (não na proposta), pro LLM ver o `ModelState` real entre blocos.

## Modelo conceitual

```
decompose(pedido) -> [sub-objetivos]
para cada sub-objetivo:
    plan_block(sub-objetivo, ModelState atual)  -> steps finos
    execute_block(steps) via run_plan_with_optional_loop  (ModelingAgentLoop corrige steps)
    observe -> capture_model_state (F1) atualiza ModelState
    avalia acceptance; se falha c/ dependentes -> replan_next_block OU aborta consistente
agrega ModelingExecutionResult
```

## Tarefas atômicas

- **T2.1** — Flag `modeling_hierarchical_planning_enabled` (`config.py`, default OFF) + doc em `docs/3d-modeling-debug.md §5`.
- **T2.2** — `DECOMPOSITION_SCHEMA` + `build_decomposition_messages` + `decompose_request` (`planner.py`). Sub-objetivo = unidade replanejável ("corpo ocado", "tampa que encaixa", "knuckle macho/fêmea", "furo do pino").
- **T2.3** — `ModelingSubGoal` + `sub_goals` em `ModelingPlan` (`contracts.py`); cada bloco é `ModelingPlan` kind=edit com `parent_plan_id`=primary (reusa maquinário de plano/execução/auditoria).
- **T2.4** — `plan_block_for_subgoal` + `replan_next_block` (`planner_service.py`): `create_llm_plan` com `edit_context`=`render_model_state_block`+descrição+concluídos.
- **T2.5** — `_run_execution_hierarchical` (`chat_orchestrator.py` + helper em `agent_loop.py`): decompõe → loop por sub-objetivo → `capture_model_state` entre blocos → avalia acceptance → `replan_next_block`/aborta. Teto `MAX_REPLAN_BLOCKS`. `_run_execution` (:132) despacha por flag.
- **T2.6** — `propose_plan` (:194) com flag ON gera decomposição e anexa `sub_goals` (planejamento fino lazy); card mostra sub-objetivos como preview.
- **T2.7** — Observabilidade: `planner.decomposed`, `orchestrator.block_started/observed/replanned/hierarchical_aborted`.
- **T2.8** — Testes mock `test_hierarchical_planning.py` (decompõe→bloco1→ModelState sintético→bloco2 com estado→agrega); flag OFF = regressão.

## Reuso

`agent_loop.ModelingAgentLoop`/`run_plan_with_optional_loop` (executa cada bloco), `planner.create_llm_plan`+`EXECUTION_PLAN_SCHEMA`, `planner_service._resolve_planner_model`/`build_corrector`, `capture_model_state` (F1), tracer/audit.

## Validação

- **Mock**: `test_hierarchical_planning.py` com `_ScriptedExecutor`+`_FakeGateway`; verificar que `ModelingAgentLoop` roda por bloco; flag OFF intacto.
- **Gate (Fusion real)**: **parafuso que ENCAIXA** — knuckle/pino macho medido via `ModelState` → furo da fêmea planejado com diâmetro real (trace mostra `planner.decomposed` + `orchestrator.block_replanned`).

## Resultado do gate (2026-05-29 — Fusion real + LLM, autônomo)

✅ **F2 VALIDADO — o encaixe funcionou.** Smoke com flags ON (`_gate_f2.py`):
pedido "bloco 40×40×20 com furo Ø10 + pino que encaixa" → o LLM **decompôs em 4
sub-objetivos** (bloco → furo Ø10 → pino Ø10×30 → verificação de encaixe), todos
`completed` como blocos `kind=edit` separados. **ModelState final:** corpo do
bloco com `raio circular 5.0mm` (furo Ø10) + `Pin_Cylinder` com `raio circular
5.0mm` (pino Ø10) — **MESMO diâmetro**. O bloco do pino foi planejado vendo o
ModelState do furo e casou a medida. É P1 (peça mecânica que encaixa) + P2
(estado real fluindo entre etapas) provados juntos. 429 testes mock verdes.

## Definição de pronto (F2)

- [x] Decomposição em sub-objetivos + planejamento lazy por bloco.
- [x] Loop observa `ModelState` (F1) entre blocos e planeja o próximo casando a medida real.
- [x] Flag OFF preserva o caminho atual (regressão verde — `test_run_execution_dispatches...`).
- [x] **Gate do parafuso/pino-que-encaixa aprovado no Fusion real** (furo Ø10 ↔ pino Ø10).
- [ ] _Follow-up_: `replan_next_block` explícito (re-planejar um bloco que falhou, hoje aborta) + verifier de aceite via LLM (hoje usa status do bloco). Sob demanda.
