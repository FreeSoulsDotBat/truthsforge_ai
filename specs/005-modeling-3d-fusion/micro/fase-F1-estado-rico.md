# Micro-plano — Frente F1: Estado rico do modelo (fundação)

**Frente**: F1 | **Spec**: [`../spec.md`](../spec.md) | **Macro**: [`../plan.md`](../plan.md) › Frentes de capacidade | **Índice**: [`../tasks.md`](../tasks.md)

> **Replan 2026-05-29**: de "cobertura de workspaces" para **capacidades de sólidos mecânicos**. F1 é a fundação que destrava P1 (peças mecânicas), P2 (planejamento), P4 (edição). Detalhe do replan em [`../../../C:/Users/Jonatan/.claude/plans/optimized-gliding-iverson.md`] (plano efêmero) — consolidado aqui.

## Objetivo

Dar ao planner **olhos e memória** sobre o modelo: identidade estável de face/edge (`entityToken`), topologia útil (adjacências, raio/eixo), e um **`ModelState` estruturado** capturado após cada execução e injetado no contexto do planner entre etapas. Hoje o `query_geometry` só dá índices posicionais frágeis e o contexto entre passos é textual — o planner não sabe *onde* colar a dobradiça / em qual face roscar.

## Estado atual (gargalos, com arquivo:função)

- `fusion_mcp_scripts.py` `_query_geometry` (~3036): faces/edges só com índice POSICIONAL; sem `entityToken`, sem adjacência, sem raio de cilíndricas.
- Selectors `_select_edges`/`_select_faces` + `_edges_by_ids`/`_faces_by_ids` (~498/512): índice posicional.
- Contexto entre etapas TEXTUAL: `chat_orchestrator._build_reconciliation_block` (~612), `planner.build_edit_context_block` (~550) — nomes de timeline/params + bbox/volume, sem geometria rica.
- `ModelingSnapshot` (`contracts.py:969`) é só arquivos, não estado geométrico.

## Decisões-chave

- **D1** — `BRepFace.entityToken`/`BRepEdge.entityToken` como identidade estável (sobrevive a recompute). Índices mantidos por compat. (Rejeitado `TF.stable_id` por face — attributes não sobrevivem a recriação de BRep, ex. fillet.)
- **D2** — `ModelState` persiste em `ModelingPlan.model_state` (JSONB → migration-free), capturado **uma vez ao fim da execução** via probe `query_geometry` fora dos steps (padrão `_read_live_timeline`).
- **D3** — `ModelState` = dado Pydantic + `render_model_state_block` (bloco `<model-state>` textual pro LLM).
- **D6** — backward-compat: campos aditivos; selectors com precedência **token > ids posicionais > selector semântico**.

## Tarefas atômicas

- **T1.1** — `_query_geometry` expõe `face_token`/`edge_token` + topologia (adjacência face↔edge via `e.faces`; raio/eixo de cilíndricas/cônicas; `is_circular`/`radius_mm` de arestas). `include_tokens` default true; respeitar `limit`; `try/except`.
- **T1.2** — Documentar em `tool_schemas.py` (`query_geometry`); fillet/chamfer/shell mencionam tokens; reforçar bloco "REFERÊNCIAS ESTÁVEIS" em `planner._build_messages` (~776).
- **T1.3** — `_edges_by_tokens`/`_faces_by_tokens` (`findEntityByToken`); branch token antes de ids em `_fillet_edges`/`_chamfer_edges`/`_shell_body`/`_collect_edges_for_patch`/`_offset_surface`/`_unstitch_surface`. Token stale → `fusion.edge_token_stale` (não cair mudo em "all").
- **T1.4** — Contrato `ModelState*` em `contracts.py` + `model_state` em `ModelingPlan`.
- **T1.5** — Novo `backend/app/modeling/model_state.py`: `model_state_from_query_output(output)` (usa `inner_fusion_payload`, tolerante) + `render_model_state_block(state)`.
- **T1.6** — `capture_model_state(executor, plan)` em `run_plan_with_optional_loop` (`agent_loop.py:372`): probe `query_geometry` via `executor._execute_single_step` fora dos steps, best-effort, grava `plan.model_state`. Só `software==fusion` com body.
- **T1.7** — Injetar `render_model_state_block` em `build_edit_context_block`/`_resolve_edit_context`/`propose_edit_plan` quando `parent_plan.model_state` existir (slot `live_state_block`).
- **T1.8** — Testes mock (`test_model_state.py` + extensões de `test_agent_loop.py` + helper de precedência) e gate.

## Reuso

`executor.inner_fusion_payload` (:110), `executor._execute_single_step` (:315), `chat_orchestrator._read_live_timeline` (:547, molde do probe), `agent_loop.run_plan_with_optional_loop` (:372), `_find_body` (:286), flag/tracer.

## Validação

- **Mock**: `test_model_state.py` (parser tolerante + render com tokens/cilíndricas); `capture_model_state` popula `plan.model_state` via `_ScriptedExecutor`; suíte verde.
- **Gate (Fusion real, autônomo via probe)**: criar body → fillet → re-`query_geometry`: face não-tocada permanece resolvível pelo MESMO token; selecionar fillet por `face_tokens` acerta a face certa; aresta consumida → erro claro `fusion.edge_token_stale`.

## Definição de pronto (F1)

- [ ] `query_geometry` expõe tokens + topologia (T1.1/T1.2).
- [ ] Selectors por token com precedência correta (T1.3).
- [ ] `ModelState` capturado e injetado entre etapas (T1.4–T1.7).
- [ ] Testes verdes; gate de estabilidade de token aprovado no Fusion real.
